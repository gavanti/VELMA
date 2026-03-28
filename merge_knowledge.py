#!/usr/bin/env python3
"""
GAVANTI - Knowledge Base Merge (Fase 4)
Deduplicación por hash y vector, sync de chunks al repo, GitHub Action
"""

import os
import sys
import json
import hashlib
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, asdict

# Configuración
DB_NAME = "knowledge.db"
SHARED_DB_NAME = "shared_knowledge.db"

# Umbrales de similitud
SIMILARITY_EXACT = 1.0
SIMILARITY_ENRICH = 0.92
SIMILARITY_CONFLICT_MIN = 0.85
SIMILARITY_CONFLICT_MAX = 0.92


@dataclass
class MergeResult:
    """Resultado de una operación de merge"""
    action: str  # 'added', 'enriched', 'conflict', 'skipped'
    source_id: int
    source_table: str
    target_id: Optional[int] = None
    similarity: float = 0.0
    message: str = ""
    
    def to_dict(self) -> Dict:
        return {
            'action': self.action,
            'source_id': self.source_id,
            'source_table': self.source_table,
            'target_id': self.target_id,
            'similarity': round(self.similarity, 4),
            'message': self.message
        }


class KnowledgeMerger:
    """Merge de conocimiento verificado al repositorio compartido"""
    
    def __init__(self, db_path: str = DB_NAME, shared_db_path: str = SHARED_DB_NAME):
        self.db_path = db_path
        self.shared_db_path = shared_db_path
        self.conn = None
        self.cursor = None
        self.shared_conn = None
        self.shared_cursor = None
        self.stats = {
            'issues_processed': 0,
            'issues_added': 0,
            'issues_enriched': 0,
            'issues_conflicts': 0,
            'issues_skipped': 0,
            'docs_processed': 0,
            'docs_added': 0,
            'docs_skipped': 0
        }
    
    def connect(self):
        """Conecta a ambas bases de datos"""
        # Base de datos local
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        
        # Base de datos compartida
        self.shared_conn = sqlite3.connect(self.shared_db_path)
        self.shared_conn.row_factory = sqlite3.Row
        self.shared_cursor = self.shared_conn.cursor()
        
        self._ensure_shared_schema()
        
        return self
    
    def close(self):
        """Cierra las conexiones"""
        if self.conn:
            self.conn.close()
        if self.shared_conn:
            self.shared_conn.close()
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _ensure_shared_schema(self):
        """Asegura que el schema de la base compartida existe"""
        # Tabla de issues compartidos
        self.shared_cursor.execute("""
            CREATE TABLE IF NOT EXISTS shared_issues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE NOT NULL,
                error TEXT NOT NULL,
                resolution TEXT,
                context TEXT,
                approach TEXT,
                attempts TEXT,  -- JSON
                tags TEXT,  -- JSON
                outcome TEXT,
                evidence TEXT,
                merged_from TEXT,  -- JSON array de source IDs
                merged_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                merged_by TEXT NOT NULL,
                owner TEXT NOT NULL,
                original_created_at TEXT
            );
        """)
        
        # Tabla de docs compartidos
        self.shared_cursor.execute("""
            CREATE TABLE IF NOT EXISTS shared_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content_hash TEXT UNIQUE NOT NULL,
                doc_source TEXT NOT NULL,
                chunk_title TEXT NOT NULL,
                chunk_body TEXT NOT NULL,
                chunk_type TEXT,
                applies_to TEXT,  -- JSON
                merged_from TEXT,  -- JSON array de source IDs
                merged_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                merged_by TEXT NOT NULL
            );
        """)
        
        # Tabla de conflictos
        self.shared_cursor.execute("""
            CREATE TABLE IF NOT EXISTS merge_conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conflict_type TEXT NOT NULL,  -- 'issue', 'doc'
                source_id INTEGER NOT NULL,
                source_table TEXT NOT NULL,
                similar_content_hash TEXT,
                similarity_score REAL,
                status TEXT DEFAULT 'pending',  -- 'pending', 'resolved', 'ignored'
                resolution TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Tabla de metadatos de sync
        self.shared_cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_type TEXT NOT NULL,
                items_processed INTEGER DEFAULT 0,
                items_added INTEGER DEFAULT 0,
                items_enriched INTEGER DEFAULT 0,
                items_conflicts INTEGER DEFAULT 0,
                synced_by TEXT NOT NULL,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        self.shared_conn.commit()
    
    # ============================================
    # Deduplicación y Similitud
    # ============================================
    
    def compute_content_hash(self, error: str, resolution: str) -> str:
        """Calcula hash del contenido para deduplicación"""
        content = f"{error or ''}|{resolution or ''}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def compute_vector_similarity(self, vec1: bytes, vec2: bytes) -> float:
        """Calcula similitud coseno entre dos vectores"""
        try:
            import numpy as np
            
            if vec1 is None or vec2 is None:
                return 0.0
            
            v1 = np.frombuffer(vec1, dtype=np.float32)
            v2 = np.frombuffer(vec2, dtype=np.float32)
            
            dot = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            
            if norm1 == 0 or norm2 == 0:
                return 0.0
            
            return float(dot / (norm1 * norm2))
        except:
            return 0.0
    
    def find_similar_issues(self, error: str, resolution: str, 
                           embedding: bytes = None) -> List[Tuple[str, float]]:
        """Busca issues similares en la base compartida"""
        similar = []
        content_hash = self.compute_content_hash(error, resolution)
        
        # 1. Buscar por hash exacto
        self.shared_cursor.execute("""
            SELECT content_hash FROM shared_issues WHERE content_hash = ?
        """, (content_hash,))
        
        if self.shared_cursor.fetchone():
            similar.append((content_hash, 1.0))
            return similar
        
        # 2. Buscar por similitud vectorial (si hay embedding)
        if embedding:
            self.shared_cursor.execute("""
                SELECT content_hash, embedding FROM shared_issues 
                WHERE embedding IS NOT NULL
            """)
            
            for row in self.shared_cursor.fetchall():
                if row['embedding']:
                    sim = self.compute_vector_similarity(embedding, row['embedding'])
                    if sim >= SIMILARITY_CONFLICT_MIN:
                        similar.append((row['content_hash'], sim))
        
        # 3. Buscar por similitud de texto (fallback)
        # Usar LIKE para encontrar errores similares
        error_words = error.split()[:5] if error else []
        if error_words:
            pattern = '%' + '%'.join(error_words) + '%'
            self.shared_cursor.execute("""
                SELECT content_hash, error FROM shared_issues 
                WHERE error LIKE ?
            """, (pattern,))
            
            for row in self.shared_cursor.fetchall():
                # Similitud simple basada en palabras comunes
                shared_words = set(row['error'].lower().split())
                local_words = set(error.lower().split())
                if shared_words and local_words:
                    intersection = shared_words & local_words
                    union = shared_words | local_words
                    sim = len(intersection) / len(union)
                    if sim >= SIMILARITY_CONFLICT_MIN:
                        similar.append((row['content_hash'], sim))
        
        # Ordenar por similitud descendente
        similar.sort(key=lambda x: x[1], reverse=True)
        return similar
    
    # ============================================
    # Merge de Issues
    # ============================================
    
    def merge_issue(self, issue: Dict, merged_by: str) -> MergeResult:
        """Mergea un issue individual"""
        issue_id = issue['id']
        error = issue['error']
        resolution = issue['resolution'] or ''
        embedding = issue.get('embedding')
        
        # Calcular hash
        content_hash = self.compute_content_hash(error, resolution)
        
        # Buscar similares
        similar = self.find_similar_issues(error, resolution, embedding)
        
        # Decidir acción según similitud
        if similar:
            best_match = similar[0]
            best_hash, best_sim = best_match
            
            if best_sim >= SIMILARITY_EXACT:
                # Hash exacto - skip
                self.stats['issues_skipped'] += 1
                return MergeResult(
                    action='skipped',
                    source_id=issue_id,
                    source_table='issues_log',
                    target_id=None,
                    similarity=best_sim,
                    message='Duplicate: exact hash match'
                )
            
            elif best_sim >= SIMILARITY_ENRICH:
                # Similitud alta - enriquecer entrada existente
                self._enrich_issue(best_hash, issue, merged_by)
                self.stats['issues_enriched'] += 1
                return MergeResult(
                    action='enriched',
                    source_id=issue_id,
                    source_table='issues_log',
                    similarity=best_sim,
                    message='Enriched existing entry with new context'
                )
            
            elif SIMILARITY_CONFLICT_MIN <= best_sim < SIMILARITY_CONFLICT_MAX:
                # Conflicto - marcar para revisión
                self._create_conflict('issue', issue_id, 'issues_log', 
                                     best_hash, best_sim)
                self.stats['issues_conflicts'] += 1
                return MergeResult(
                    action='conflict',
                    source_id=issue_id,
                    source_table='issues_log',
                    similarity=best_sim,
                    message='Conflict: similar entry exists, needs review'
                )
        
        # No hay similares - agregar nuevo
        self._add_new_issue(issue, content_hash, merged_by)
        self.stats['issues_added'] += 1
        return MergeResult(
            action='added',
            source_id=issue_id,
            source_table='issues_log',
            similarity=0.0,
            message='New entry added to shared knowledge'
        )
    
    def _add_new_issue(self, issue: Dict, content_hash: str, merged_by: str):
        """Agrega un nuevo issue a la base compartida"""
        self.shared_cursor.execute("""
            INSERT INTO shared_issues 
            (content_hash, error, resolution, context, approach, attempts, tags,
             outcome, evidence, merged_from, merged_by, owner, original_created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            content_hash,
            issue['error'],
            issue['resolution'],
            issue['context'],
            issue['approach'],
            issue['attempts'],
            issue['tags'],
            issue['outcome'],
            issue['evidence'],
            json.dumps([issue['id']]),
            merged_by,
            issue['owner'],
            issue['created_at']
        ))
        
        self.shared_conn.commit()
    
    def _enrich_issue(self, content_hash: str, new_issue: Dict, merged_by: str):
        """Enriquece un issue existente con nueva información"""
        # Obtener entrada existente
        self.shared_cursor.execute("""
            SELECT * FROM shared_issues WHERE content_hash = ?
        """, (content_hash,))
        
        existing = self.shared_cursor.fetchone()
        if not existing:
            return
        
        # Actualizar merged_from para incluir nueva fuente
        merged_from = json.loads(existing['merged_from'] or '[]')
        if new_issue['id'] not in merged_from:
            merged_from.append(new_issue['id'])
        
        # Enriquecer contexto si hay información nueva
        new_context = new_issue.get('context', '')
        existing_context = existing['context'] or ''
        
        if new_context and new_context not in existing_context:
            enriched_context = existing_context + f"\n\n[Additional context from issue #{new_issue['id']}]\n{new_context}"
        else:
            enriched_context = existing_context
        
        # Actualizar
        self.shared_cursor.execute("""
            UPDATE shared_issues 
            SET merged_from = ?, context = ?, merged_at = ?, merged_by = ?
            WHERE content_hash = ?
        """, (
            json.dumps(merged_from),
            enriched_context,
            datetime.now().isoformat(),
            merged_by,
            content_hash
        ))
        
        self.shared_conn.commit()
    
    def _create_conflict(self, conflict_type: str, source_id: int, 
                        source_table: str, similar_hash: str, 
                        similarity: float):
        """Crea un registro de conflicto para revisión manual"""
        self.shared_cursor.execute("""
            INSERT INTO merge_conflicts 
            (conflict_type, source_id, source_table, similar_content_hash, similarity_score)
            VALUES (?, ?, ?, ?, ?)
        """, (conflict_type, source_id, source_table, similar_hash, similarity))
        
        self.shared_conn.commit()
    
    # ============================================
    # Merge de Documentos
    # ============================================
    
    def merge_doc(self, doc: Dict, merged_by: str) -> MergeResult:
        """Mergea un documento/chunk individual"""
        doc_id = doc['id']
        chunk_title = doc['chunk_title']
        chunk_body = doc['chunk_body']
        
        # Calcular hash
        content_hash = self.compute_content_hash(chunk_title, chunk_body)
        
        # Verificar si ya existe
        self.shared_cursor.execute("""
            SELECT id FROM shared_docs WHERE content_hash = ?
        """, (content_hash,))
        
        if self.shared_cursor.fetchone():
            self.stats['docs_skipped'] += 1
            return MergeResult(
                action='skipped',
                source_id=doc_id,
                source_table='docs_index',
                message='Duplicate: exact hash match'
            )
        
        # Agregar nuevo
        self._add_new_doc(doc, content_hash, merged_by)
        self.stats['docs_added'] += 1
        return MergeResult(
            action='added',
            source_id=doc_id,
            source_table='docs_index',
            message='New doc chunk added to shared knowledge'
        )
    
    def _add_new_doc(self, doc: Dict, content_hash: str, merged_by: str):
        """Agrega un nuevo doc chunk a la base compartida"""
        self.shared_cursor.execute("""
            INSERT INTO shared_docs 
            (content_hash, doc_source, chunk_title, chunk_body, chunk_type,
             applies_to, merged_from, merged_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            content_hash,
            doc['doc_source'],
            doc['chunk_title'],
            doc['chunk_body'],
            doc['chunk_type'],
            doc['applies_to'],
            json.dumps([doc['id']]),
            merged_by
        ))
        
        self.shared_conn.commit()
    
    # ============================================
    # Proceso de Merge Principal
    # ============================================
    
    def merge_all(self, merged_by: str = None, dry_run: bool = False) -> List[MergeResult]:
        """
        Ejecuta el proceso completo de merge.
        
        Args:
            merged_by: Nombre del desarrollador que ejecuta el merge
            dry_run: Si True, no modifica la base de datos
            
        Returns:
            Lista de resultados de merge
        """
        results = []
        
        if merged_by is None:
            merged_by = os.environ.get('DEV_NAME', 'unknown')
        
        print(f"\n{'='*60}")
        print(f"  MERGE KNOWLEDGE - {merged_by}")
        print(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        print(f"{'='*60}\n")
        
        # 1. Mergear issues verificados
        print("📋 Procesando issues verificados...")
        self.cursor.execute("""
            SELECT * FROM issues_log 
            WHERE status = 'verified' AND (shared_id IS NULL OR shared_id = 0)
        """)
        
        issues = [dict(row) for row in self.cursor.fetchall()]
        print(f"   Encontrados: {len(issues)} issues para mergear")
        
        for issue in issues:
            result = self.merge_issue(issue, merged_by)
            results.append(result)
            
            if result.action == 'added' and not dry_run:
                # Actualizar shared_id en la tabla local
                self.shared_cursor.execute("""
                    SELECT id FROM shared_issues 
                    WHERE content_hash = ?
                """, (self.compute_content_hash(issue['error'], issue['resolution'] or ''),))
                
                shared = self.shared_cursor.fetchone()
                if shared:
                    self.cursor.execute("""
                        UPDATE issues_log 
                        SET status = 'merged', shared_id = ?
                        WHERE id = ?
                    """, (shared['id'], issue['id']))
                    self.conn.commit()
        
        self.stats['issues_processed'] = len(issues)
        
        # 2. Mergear documentos verificados
        print("\n📚 Procesando documentos verificados...")
        self.cursor.execute("""
            SELECT * FROM docs_index WHERE verified = 1
        """)
        
        docs = [dict(row) for row in self.cursor.fetchall()]
        print(f"   Encontrados: {len(docs)} docs para mergear")
        
        for doc in docs:
            result = self.merge_doc(doc, merged_by)
            results.append(result)
        
        self.stats['docs_processed'] = len(docs)
        
        # 3. Registrar sync en metadatos
        if not dry_run:
            self.shared_cursor.execute("""
                INSERT INTO sync_metadata 
                (sync_type, items_processed, items_added, items_enriched, 
                 items_conflicts, synced_by)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                'merge',
                self.stats['issues_processed'] + self.stats['docs_processed'],
                self.stats['issues_added'] + self.stats['docs_added'],
                self.stats['issues_enriched'],
                self.stats['issues_conflicts'],
                merged_by
            ))
            self.shared_conn.commit()
        
        return results
    
    def print_stats(self):
        """Imprime estadísticas del merge"""
        print(f"\n{'='*60}")
        print("  ESTADÍSTICAS DE MERGE")
        print(f"{'='*60}")
        print(f"  Issues procesados: {self.stats['issues_processed']}")
        print(f"    - Agregados: {self.stats['issues_added']}")
        print(f"    - Enriquecidos: {self.stats['issues_enriched']}")
        print(f"    - Conflictos: {self.stats['issues_conflicts']}")
        print(f"    - Omitidos: {self.stats['issues_skipped']}")
        print(f"  Documentos procesados: {self.stats['docs_processed']}")
        print(f"    - Agregados: {self.stats['docs_added']}")
        print(f"    - Omitidos: {self.stats['docs_skipped']}")
        print(f"{'='*60}\n")
    
    def get_conflicts(self) -> List[Dict]:
        """Obtiene lista de conflictos pendientes"""
        self.shared_cursor.execute("""
            SELECT * FROM merge_conflicts 
            WHERE status = 'pending'
            ORDER BY created_at DESC
        """)
        
        return [dict(row) for row in self.shared_cursor.fetchall()]
    
    def resolve_conflict(self, conflict_id: int, resolution: str, 
                        action: str = 'resolved') -> bool:
        """
        Resuelve un conflicto.
        
        Args:
            conflict_id: ID del conflicto
            resolution: Descripción de la resolución
            action: 'resolved' o 'ignored'
        """
        self.shared_cursor.execute("""
            UPDATE merge_conflicts 
            SET status = ?, resolution = ?
            WHERE id = ?
        """, (action, resolution, conflict_id))
        
        self.shared_conn.commit()
        return True


# ============================================
# CLI Interface
# ============================================

def main():
    """Función principal"""
    parser = argparse.ArgumentParser(
        description='GAVANTI Knowledge Base Merge - Deduplicación y sync'
    )
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Simular merge sin modificar bases de datos'
    )
    parser.add_argument(
        '--output', '-o',
        help='Archivo JSON para guardar resultados'
    )
    parser.add_argument(
        '--merged-by',
        default=None,
        help='Nombre del desarrollador (default: env DEV_NAME)'
    )
    parser.add_argument(
        '--conflicts', '-c',
        action='store_true',
        help='Mostrar conflictos pendientes'
    )
    parser.add_argument(
        '--resolve',
        type=int,
        help='Resolver conflicto con ID especificado'
    )
    parser.add_argument(
        '--resolution',
        default='Manual resolution',
        help='Descripción de la resolución'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("  GAVANTI - Knowledge Base Merge (Fase 4)")
    print("  Deduplicación y sincronización")
    print("="*60)
    
    with KnowledgeMerger() as merger:
        # Mostrar conflictos
        if args.conflicts:
            conflicts = merger.get_conflicts()
            print(f"\n📋 Conflictos pendientes: {len(conflicts)}")
            for conflict in conflicts:
                print(f"\n  #{conflict['id']}: {conflict['conflict_type']}")
                print(f"     Source: {conflict['source_table']} #{conflict['source_id']}")
                print(f"     Similitud: {conflict['similarity_score']:.3f}")
                print(f"     Creado: {conflict['created_at']}")
            return 0
        
        # Resolver conflicto
        if args.resolve:
            success = merger.resolve_conflict(args.resolve, args.resolution)
            if success:
                print(f"✅ Conflicto #{args.resolve} resuelto")
            else:
                print(f"❌ Error resolviendo conflicto #{args.resolve}")
            return 0
        
        # Ejecutar merge
        results = merger.merge_all(
            merged_by=args.merged_by,
            dry_run=args.dry_run
        )
        
        # Imprimir estadísticas
        merger.print_stats()
        
        # Guardar resultados si se especificó
        if args.output:
            output_data = {
                'timestamp': datetime.now().isoformat(),
                'dry_run': args.dry_run,
                'stats': merger.stats,
                'results': [r.to_dict() for r in results]
            }
            
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            print(f"✅ Resultados guardados en: {args.output}")
        
        # Resumen
        print("📊 Resumen de acciones:")
        action_counts = {}
        for r in results:
            action_counts[r.action] = action_counts.get(r.action, 0) + 1
        
        for action, count in sorted(action_counts.items()):
            print(f"   {action}: {count}")
    
    print("\n✅ Merge completado")
    return 0


if __name__ == "__main__":
    sys.exit(main())
