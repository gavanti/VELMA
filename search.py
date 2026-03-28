#!/usr/bin/env python3
"""
VELMA - Knowledge Base Search (Fase 3)
Búsqueda híbrida FTS5+vector con RRF, panel HTML/JS para revisar y verificar entradas
"""

import os
import re
import sqlite3
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass

# Flask para el panel web
from flask import Flask, render_template, request, jsonify, redirect, url_for

# Embeddings y similitud
from kb_utils import cosine_similarity, encode_text, OllamaEnricher

# Configuración
DB_NAME = "knowledge.db"
DEFAULT_K = 60   # Constante para RRF
MIN_CONFIDENCE_SCORE = 0.50
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2:1b')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'velma-kb-secret-key')
app.config['PROJECT_NAME'] = os.getenv('PROJECT_NAME', 'VELMA')

@app.context_processor
def inject_project():
    """Inyecta project_name en todos los templates."""
    return {'project_name': app.config['PROJECT_NAME']}


@dataclass
class SearchResult:
    """Resultado de búsqueda"""
    id: int
    table: str
    title: str
    content: str
    score: float
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'table': self.table,
            'title': self.title,
            'content': self.content[:500] + '...' if len(self.content) > 500 else self.content,
            'score': round(self.score, 4),
            'metadata': self.metadata
        }


class KnowledgeSearch:
    """Motor de búsqueda híbrida para el knowledge base"""
    
    def __init__(self, db_path: str = DB_NAME, use_ollama: bool = True):
        self.db_path = db_path
        self.use_ollama = use_ollama
        self.enricher = OllamaEnricher(model=OLLAMA_MODEL) if use_ollama else None
        self.conn = None
        self.cursor = None
    
    def connect(self):
        """Conecta a la base de datos"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        return self
    
    def close(self):
        """Cierra la conexión"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # ============================================
    # Búsqueda FTS5
    # ============================================
    
    def search_fts_issues(self, query: str, limit: int = 20) -> List[Tuple[int, float]]:
        """Busca en issues_log usando FTS5"""
        try:
            # Usar MATCH de FTS5
            self.cursor.execute("""
                SELECT rowid, rank
                FROM issues_log_fts
                WHERE issues_log_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            results = []
            for row in self.cursor.fetchall():
                # Convertir rank FTS5 a score (más alto es mejor)
                # FTS5 rank es negativo, menor es mejor match
                rank = row['rank'] if row['rank'] else -1000
                score = 1.0 / (1.0 + abs(rank))
                results.append((row['rowid'], score))
            
            return results
        except Exception as e:
            print(f"FTS issues error: {e}")
            return []
    
    def search_fts_docs(self, query: str, limit: int = 20) -> List[Tuple[int, float]]:
        """Busca en docs_index usando FTS5"""
        try:
            self.cursor.execute("""
                SELECT rowid, rank
                FROM docs_index_fts
                WHERE docs_index_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            results = []
            for row in self.cursor.fetchall():
                rank = row['rank'] if row['rank'] else -1000
                score = 1.0 / (1.0 + abs(rank))
                results.append((row['rowid'], score))
            
            return results
        except Exception as e:
            print(f"FTS docs error: {e}")
            return []
    
    def search_fts_files(self, query: str, limit: int = 20) -> List[Tuple[int, float]]:
        """Busca en files_index usando FTS5"""
        try:
            self.cursor.execute("""
                SELECT rowid, rank
                FROM files_index_fts
                WHERE files_index_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            results = []
            for row in self.cursor.fetchall():
                rank = row['rank'] if row['rank'] else -1000
                score = 1.0 / (1.0 + abs(rank))
                results.append((row['rowid'], score))
            
            return results
        except Exception as e:
            print(f"FTS files error: {e}")
            return []
    
    def search_fts_reasoning(self, query: str, limit: int = 20) -> List[Tuple[int, float]]:
        """Busca en reasoning_log usando FTS5"""
        try:
            self.cursor.execute("""
                SELECT rowid, rank
                FROM reasoning_log_fts
                WHERE reasoning_log_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit))
            
            results = []
            for row in self.cursor.fetchall():
                rank = row['rank'] if row['rank'] else -1000
                score = 1.0 / (1.0 + abs(rank))
                results.append((row['rowid'], score))
            
            return results
        except Exception as e:
            print(f"FTS reasoning error: {e}")
            return []
    
    # ============================================
    # RRF - Reciprocal Rank Fusion
    # ============================================
    
    def reciprocal_rank_fusion(self, rankings: List[List[Tuple[int, float]]], 
                                k: int = DEFAULT_K) -> Dict[int, float]:
        """
        Combina múltiples rankings usando Reciprocal Rank Fusion.
        
        Args:
            rankings: Lista de listas de (id, score)
            k: Constante de suavizado
            
        Returns:
            Dict de id -> score fusionado
        """
        scores = {}
        
        for ranking in rankings:
            for rank, (doc_id, _) in enumerate(ranking):
                if doc_id not in scores:
                    scores[doc_id] = 0
                # RRF score: 1 / (k + rank)
                scores[doc_id] += 1.0 / (k + rank + 1)
        
        return scores
    
    # ============================================
    # Búsqueda Vectorial
    # ============================================

    def search_vector_issues(self, query_embedding: bytes, limit: int = 20) -> List[Tuple[int, float]]:
        """Búsqueda por similitud coseno en issues_log."""
        if query_embedding is None:
            return []
        try:
            self.cursor.execute("""
                SELECT id, embedding FROM issues_log
                WHERE embedding IS NOT NULL
            """)
            results = []
            for row in self.cursor.fetchall():
                sim = cosine_similarity(query_embedding, row['embedding'])
                if sim >= MIN_CONFIDENCE_SCORE:
                    results.append((row['id'], sim))
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
        except Exception as e:
            print(f"Vector issues error: {e}")
            return []

    def search_vector_docs(self, query_embedding: bytes, limit: int = 20) -> List[Tuple[int, float]]:
        """Búsqueda por similitud coseno en docs_index."""
        if query_embedding is None:
            return []
        try:
            self.cursor.execute("""
                SELECT id, embedding FROM docs_index
                WHERE embedding IS NOT NULL
            """)
            results = []
            for row in self.cursor.fetchall():
                sim = cosine_similarity(query_embedding, row['embedding'])
                if sim >= MIN_CONFIDENCE_SCORE:
                    results.append((row['id'], sim))
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
        except Exception as e:
            print(f"Vector docs error: {e}")
            return []

    # ============================================
    # Búsqueda Híbrida
    # ============================================

    def search_issues(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Busca en issues_log con búsqueda híbrida FTS5 + vector + RRF."""
        # FTS5 (usa query original para exact match)
        fts_results = self.search_fts_issues(query, limit * 2)

        # Vector (enriquecimiento bilingüe con Ollama)
        try:
            vector_query = query
            if self.enricher and self.enricher.available:
                vector_query = self.enricher.translate_and_enrich(query)
            
            query_emb = encode_text(vector_query)
            vector_results = self.search_vector_issues(query_emb, limit * 2)
        except Exception:
            query_emb = None
            vector_results = []

        # RRF fusion
        if vector_results:
            fused = self.reciprocal_rank_fusion([fts_results, vector_results])
            top = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:limit]
            doc_ids = [doc_id for doc_id, _ in top]
            score_map = dict(top)
        else:
            # Sin embeddings → solo FTS5
            doc_ids = [doc_id for doc_id, _ in fts_results[:limit]]
            score_map = {doc_id: score for doc_id, score in fts_results[:limit]}

        if not doc_ids:
            return []

        placeholders = ','.join('?' * len(doc_ids))
        self.cursor.execute(f"""
            SELECT id, error, resolution, context, status, outcome,
                   owner, created_at, tags
            FROM issues_log
            WHERE id IN ({placeholders})
        """, doc_ids)

        rows = {row['id']: row for row in self.cursor.fetchall()}
        results = []
        for doc_id in doc_ids:
            if doc_id in rows:
                row = rows[doc_id]
                results.append(SearchResult(
                    id=row['id'],
                    table='issues_log',
                    title=row['error'][:100],
                    content=f"Error: {row['error']}\n\nResolucion: {row['resolution'] or 'N/A'}",
                    score=score_map.get(doc_id, 0.0),
                    metadata={
                        'status': row['status'],
                        'outcome': row['outcome'],
                        'owner': row['owner'],
                        'created_at': row['created_at'],
                        'tags': row['tags']
                    }
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results

    def search_docs(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Busca en docs_index con búsqueda híbrida FTS5 + vector + RRF."""
        # FTS5
        fts_results = self.search_fts_docs(query, limit * 2)

        # Vector (enriquecimiento bilingüe con Ollama)
        try:
            vector_query = query
            if self.enricher and self.enricher.available:
                vector_query = self.enricher.translate_and_enrich(query)
            
            query_emb = encode_text(vector_query)
            vector_results = self.search_vector_docs(query_emb, limit * 2)
        except Exception:
            query_emb = None
            vector_results = []

        # RRF fusion
        if vector_results:
            fused = self.reciprocal_rank_fusion([fts_results, vector_results])
            top = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:limit]
            doc_ids = [doc_id for doc_id, _ in top]
            score_map = dict(top)
        else:
            doc_ids = [doc_id for doc_id, _ in fts_results[:limit]]
            score_map = {doc_id: score for doc_id, score in fts_results[:limit]}

        if not doc_ids:
            return []

        placeholders = ','.join('?' * len(doc_ids))
        self.cursor.execute(f"""
            SELECT id, doc_source, chunk_title, chunk_body, chunk_type,
                   verified, applies_to
            FROM docs_index
            WHERE id IN ({placeholders})
        """, doc_ids)

        rows = {row['id']: row for row in self.cursor.fetchall()}
        results = []
        for doc_id in doc_ids:
            if doc_id in rows:
                row = rows[doc_id]
                # Aplicar peso de chunk sobre el score RRF/FTS5
                weight = self._get_chunk_weight(row['chunk_type'])
                raw_score = score_map.get(doc_id, 0.0)
                adjusted_score = raw_score * (weight / 10)

                results.append(SearchResult(
                    id=row['id'],
                    table='docs_index',
                    title=f"[{row['chunk_type'].upper()}] {row['chunk_title']}",
                    content=row['chunk_body'],
                    score=adjusted_score,
                    metadata={
                        'doc_source': row['doc_source'],
                        'chunk_type': row['chunk_type'],
                        'verified': row['verified'],
                        'applies_to': row['applies_to']
                    }
                ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    def search_files(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Busca en files_index"""
        fts_results = self.search_fts_files(query, limit)
        
        doc_ids = [doc_id for doc_id, _ in fts_results]
        
        if not doc_ids:
            return []
        
        results = []
        placeholders = ','.join('?' * len(doc_ids))
        self.cursor.execute(f"""
            SELECT rowid, path, summary, language, computed_at
            FROM files_index
            WHERE rowid IN ({placeholders})
        """, doc_ids)
        
        rows = {row['rowid']: row for row in self.cursor.fetchall()}
        
        for doc_id, fts_score in fts_results:
            if doc_id in rows:
                row = rows[doc_id]
                results.append(SearchResult(
                    id=row['rowid'],
                    table='files_index',
                    title=row['path'],
                    content=row['summary'] or 'Sin descripción',
                    score=fts_score,
                    metadata={
                        'language': row['language'],
                        'computed_at': row['computed_at']
                    }
                ))
        
        return results
    
    def search_reasoning(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Busca en reasoning_log"""
        fts_results = self.search_fts_reasoning(query, limit)
        
        doc_ids = [doc_id for doc_id, _ in fts_results]
        
        if not doc_ids:
            return []
        
        results = []
        placeholders = ','.join('?' * len(doc_ids))
        self.cursor.execute(f"""
            SELECT id, task, approach, outcome, status, owner, created_at
            FROM reasoning_log
            WHERE id IN ({placeholders})
        """, doc_ids)
        
        rows = {row['id']: row for row in self.cursor.fetchall()}
        
        for doc_id, fts_score in fts_results:
            if doc_id in rows:
                row = rows[doc_id]
                results.append(SearchResult(
                    id=row['id'],
                    table='reasoning_log',
                    title=row['task'][:100],
                    content=f"Enfoque: {row['approach']}\n\nResultado: {row['outcome'] or 'N/A'}",
                    score=fts_score,
                    metadata={
                        'status': row['status'],
                        'owner': row['owner'],
                        'created_at': row['created_at']
                    }
                ))
        
        return results
    
    def search_all(self, query: str, limit: int = 10) -> Dict[str, List[SearchResult]]:
        """Busca en todas las tablas"""
        return {
            'issues': self.search_issues(query, limit),
            'docs': self.search_docs(query, limit),
            'files': self.search_files(query),
            'reasoning': self.search_reasoning(query)
        }
    
    def _get_chunk_weight(self, chunk_type: str) -> int:
        """Retorna el peso de un tipo de chunk"""
        weights = {
            'constraint': 10,
            'rule': 8,
            'procedure': 7,
            'concept': 5,
            'example': 3
        }
        return weights.get(chunk_type, 5)
    
    # ============================================
    # Gestión de Issues
    # ============================================
    
    def get_issue(self, issue_id: int) -> Optional[Dict]:
        """Obtiene un issue por ID"""
        self.cursor.execute("""
            SELECT * FROM issues_log WHERE id = ?
        """, (issue_id,))
        
        row = self.cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def update_issue_status(self, issue_id: int, status: str, verified_by: str = None):
        """Actualiza el estado de un issue"""
        if status == 'verified':
            self.cursor.execute("""
                UPDATE issues_log 
                SET status = ?, verified_by = ?, verified_at = ?
                WHERE id = ?
            """, (status, verified_by, datetime.now().isoformat(), issue_id))
        elif status == 'archived':
            self.cursor.execute("""
                UPDATE issues_log 
                SET status = ?
                WHERE id = ?
            """, (status, issue_id))
        else:
            self.cursor.execute("""
                UPDATE issues_log 
                SET status = ?
                WHERE id = ?
            """, (status, issue_id))
        
        self.conn.commit()
        return True
    
    def get_pending_issues(self, limit: int = 50) -> List[Dict]:
        """Obtiene issues pendientes de verificación"""
        self.cursor.execute("""
            SELECT * FROM issues_log 
            WHERE status = 'raw'
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    def get_all_issues(self, status: str = None, limit: int = 100) -> List[Dict]:
        """Obtiene todos los issues"""
        if status:
            self.cursor.execute("""
                SELECT * FROM issues_log 
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (status, limit))
        else:
            self.cursor.execute("""
                SELECT * FROM issues_log 
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        
        return [dict(row) for row in self.cursor.fetchall()]
    
    # ============================================
    # Estadísticas
    # ============================================
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del knowledge base"""
        stats = {}
        
        for table in ['issues_log', 'docs_index', 'files_index', 'reasoning_log', 'functions_index']:
            self.cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = self.cursor.fetchone()[0]
        
        # Issues por estado
        self.cursor.execute("""
            SELECT status, COUNT(*) FROM issues_log GROUP BY status
        """)
        stats['issues_by_status'] = {row[0]: row[1] for row in self.cursor.fetchall()}
        
        # Docs por tipo
        self.cursor.execute("""
            SELECT chunk_type, COUNT(*) FROM docs_index GROUP BY chunk_type
        """)
        stats['docs_by_type'] = {row[0]: row[1] for row in self.cursor.fetchall()}
        
        return stats


# ============================================
# CLI Interface
# ============================================

def cli_search():
    """Interfaz de línea de comandos para búsqueda"""
    parser = argparse.ArgumentParser(description='VELMA Knowledge Base Search')
    parser.add_argument('query', help='Término de búsqueda')
    parser.add_argument('--table', '-t', choices=['issues', 'docs', 'files', 'reasoning', 'all'],
                        default='all', help='Tabla a buscar')
    parser.add_argument('--limit', '-l', type=int, default=10, help='Límite de resultados')
    parser.add_argument('--json', '-j', action='store_true', help='Output en JSON')
    
    args = parser.parse_args()
    
    with KnowledgeSearch() as search:
        if args.table == 'all':
            results = search.search_all(args.query, args.limit)
        elif args.table == 'issues':
            results = {'issues': search.search_issues(args.query, args.limit)}
        elif args.table == 'docs':
            results = {'docs': search.search_docs(args.query, args.limit)}
        elif args.table == 'files':
            results = {'files': search.search_files(args.query)}
        elif args.table == 'reasoning':
            results = {'reasoning': search.search_reasoning(args.query)}
        
        if args.json:
            # Convertir a dict para JSON
            json_results = {}
            for table, items in results.items():
                json_results[table] = [item.to_dict() for item in items]
            print(json.dumps(json_results, indent=2, ensure_ascii=False))
        else:
            # Output formateado
            print("="*60)
            print(f"  Resultados para: '{args.query}'")
            print("="*60)
            
            for table, items in results.items():
                if items:
                    print(f"\n📁 {table.upper()} ({len(items)} resultados)")
                    print("-"*40)
                    for item in items:
                        print(f"  [{item.score:.3f}] {item.title}")
                        if item.table == 'issues_log':
                            print(f"      Status: {item.metadata.get('status', 'N/A')}")
                        elif item.table == 'docs_index':
                            print(f"      Type: {item.metadata.get('chunk_type', 'N/A')}")


# ============================================
# Web Panel Routes
# ============================================

@app.route('/')
def index():
    """Página principal del panel"""
    with KnowledgeSearch() as search:
        stats = search.get_stats()
    
    return render_template('index.html', stats=stats)


@app.route('/search')
def search_page():
    """Página de búsqueda"""
    query = request.args.get('q', '')
    results = None
    
    if query:
        with KnowledgeSearch() as search:
            results = search.search_all(query, limit=10)
            # Convertir a dict para template
            for table in results:
                results[table] = [r.to_dict() for r in results[table]]
    
    return render_template('search.html', query=query, results=results)


@app.route('/api/search')
def api_search():
    """API endpoint para búsqueda"""
    query = request.args.get('q', '')
    table = request.args.get('table', 'all')
    limit = int(request.args.get('limit', 10))
    
    if not query:
        return jsonify({'error': 'Query required'}), 400
    
    with KnowledgeSearch() as search:
        if table == 'all':
            results = search.search_all(query, limit)
        elif table == 'issues':
            results = {'issues': search.search_issues(query, limit)}
        elif table == 'docs':
            results = {'docs': search.search_docs(query, limit)}
        elif table == 'files':
            results = {'files': search.search_files(query)}
        elif table == 'reasoning':
            results = {'reasoning': search.search_reasoning(query)}
        else:
            return jsonify({'error': 'Invalid table'}), 400
        
        # Convertir a dict
        json_results = {}
        for t, items in results.items():
            json_results[t] = [item.to_dict() for item in items]
        
        return jsonify({
            'query': query,
            'results': json_results,
            'total': sum(len(items) for items in json_results.values())
        })


@app.route('/issues')
def issues_page():
    """Página de gestión de issues"""
    status = request.args.get('status', None)
    
    with KnowledgeSearch() as search:
        issues = search.get_all_issues(status=status, limit=100)
    
    return render_template('issues.html', issues=issues, current_status=status)


@app.route('/api/issues/<int:issue_id>', methods=['GET'])
def api_get_issue(issue_id):
    """API: Obtener un issue"""
    with KnowledgeSearch() as search:
        issue = search.get_issue(issue_id)
        if issue:
            return jsonify(issue)
        return jsonify({'error': 'Issue not found'}), 404


@app.route('/api/issues/<int:issue_id>/status', methods=['POST'])
def api_update_issue_status(issue_id):
    """API: Actualizar estado de un issue"""
    data = request.get_json()
    status = data.get('status')
    verified_by = data.get('verified_by', 'web-panel')
    
    if status not in ['raw', 'verified', 'merged', 'archived']:
        return jsonify({'error': 'Invalid status'}), 400
    
    with KnowledgeSearch() as search:
        success = search.update_issue_status(issue_id, status, verified_by)
        if success:
            return jsonify({'success': True, 'issue_id': issue_id, 'status': status})
        return jsonify({'error': 'Update failed'}), 500


@app.route('/api/stats')
def api_stats():
    """API: Estadísticas del knowledge base"""
    with KnowledgeSearch() as search:
        stats = search.get_stats()
        return jsonify(stats)


def create_templates():
    """Crea los templates HTML para el panel web"""
    templates_dir = Path('templates')
    templates_dir.mkdir(exist_ok=True)
    
    # Template base
    base_template = '''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}VELMA Knowledge Base{% endblock %}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header {
            background: linear-gradient(135deg, #1e293b 0%, #334155 100%);
            padding: 20px 0;
            margin-bottom: 30px;
            border-bottom: 2px solid #3b82f6;
        }
        header h1 { font-size: 1.8rem; color: #60a5fa; }
        header p { color: #94a3b8; margin-top: 5px; }
        nav {
            background: #1e293b;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            gap: 20px;
        }
        nav a {
            color: #94a3b8;
            text-decoration: none;
            padding: 8px 16px;
            border-radius: 4px;
            transition: all 0.2s;
        }
        nav a:hover, nav a.active {
            background: #3b82f6;
            color: white;
        }
        .card {
            background: #1e293b;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #334155;
        }
        .card h2 {
            color: #60a5fa;
            margin-bottom: 15px;
            font-size: 1.2rem;
        }
        .search-box {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
        }
        .search-box input {
            flex: 1;
            padding: 12px 16px;
            border: 1px solid #334155;
            border-radius: 6px;
            background: #0f172a;
            color: #e2e8f0;
            font-size: 1rem;
        }
        .search-box button {
            padding: 12px 24px;
            background: #3b82f6;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1rem;
        }
        .search-box button:hover { background: #2563eb; }
        .result-item {
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 6px;
            padding: 15px;
            margin-bottom: 10px;
        }
        .result-item h3 {
            color: #60a5fa;
            font-size: 1rem;
            margin-bottom: 8px;
        }
        .result-item .meta {
            color: #64748b;
            font-size: 0.85rem;
            margin-bottom: 10px;
        }
        .result-item .content {
            color: #cbd5e1;
            font-size: 0.9rem;
            white-space: pre-wrap;
            max-height: 150px;
            overflow: hidden;
        }
        .score {
            display: inline-block;
            background: #3b82f6;
            color: white;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.8rem;
            margin-left: 10px;
        }
        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            margin-right: 5px;
        }
        .badge-raw { background: #f59e0b; color: #000; }
        .badge-verified { background: #10b981; color: #000; }
        .badge-merged { background: #3b82f6; color: #fff; }
        .badge-archived { background: #6b7280; color: #fff; }
        .badge-constraint { background: #ef4444; color: #fff; }
        .badge-rule { background: #f97316; color: #fff; }
        .badge-procedure { background: #8b5cf6; color: #fff; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        .stat-card {
            background: #0f172a;
            padding: 15px;
            border-radius: 6px;
            text-align: center;
        }
        .stat-card .number {
            font-size: 2rem;
            font-weight: bold;
            color: #60a5fa;
        }
        .stat-card .label {
            color: #64748b;
            font-size: 0.9rem;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #334155;
        }
        th {
            color: #94a3b8;
            font-weight: 500;
        }
        .actions {
            display: flex;
            gap: 5px;
        }
        .btn {
            padding: 4px 12px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8rem;
        }
        .btn-verify { background: #10b981; color: #000; }
        .btn-archive { background: #6b7280; color: #fff; }
    </style>
    {% block extra_css %}{% endblock %}
</head>
<body>
    <header>
        <div class="container">
            <h1>🔷 VELMA Knowledge Base</h1>
            <p>Sistema de Memoria Persistente para Agentes de IA</p>
        </div>
    </header>
    
    <div class="container">
        <nav>
            <a href="/" {% if request.path == '/' %}class="active"{% endif %}>Dashboard</a>
            <a href="/search" {% if request.path == '/search' %}class="active"{% endif %}>Buscar</a>
            <a href="/issues" {% if request.path == '/issues' %}class="active"{% endif %}>Issues</a>
        </nav>
        
        {% block content %}{% endblock %}
    </div>
    
    {% block extra_js %}{% endblock %}
</body>
</html>'''
    
    # Template index (dashboard)
    index_template = '''{% extends "base.html" %}

{% block title %}Dashboard - GAVANTI KB{% endblock %}

{% block content %}
<div class="card">
    <h2>📊 Estadísticas del Knowledge Base</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <div class="number">{{ stats.issues_log }}</div>
            <div class="label">Issues</div>
        </div>
        <div class="stat-card">
            <div class="number">{{ stats.docs_index }}</div>
            <div class="label">Documentos</div>
        </div>
        <div class="stat-card">
            <div class="number">{{ stats.files_index }}</div>
            <div class="label">Archivos</div>
        </div>
        <div class="stat-card">
            <div class="number">{{ stats.functions_index }}</div>
            <div class="label">Funciones</div>
        </div>
        <div class="stat-card">
            <div class="number">{{ stats.reasoning_log }}</div>
            <div class="label">Razonamientos</div>
        </div>
    </div>
</div>

<div class="card">
    <h2>📋 Issues por Estado</h2>
    <div class="stats-grid">
        {% for status, count in stats.issues_by_status.items() %}
        <div class="stat-card">
            <div class="number">{{ count }}</div>
            <div class="label">{{ status }}</div>
        </div>
        {% endfor %}
    </div>
</div>

<div class="card">
    <h2>📚 Documentos por Tipo</h2>
    <div class="stats-grid">
        {% for type, count in stats.docs_by_type.items() %}
        <div class="stat-card">
            <div class="number">{{ count }}</div>
            <div class="label">{{ type }}</div>
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}'''
    
    # Template search
    search_template = '''{% extends "base.html" %}

{% block title %}Buscar - GAVANTI KB{% endblock %}

{% block content %}
<div class="card">
    <h2>🔍 Búsqueda Híbrida (FTS5 + RRF)</h2>
    <form class="search-box" action="/search" method="get">
        <input type="text" name="q" placeholder="Buscar en el knowledge base..." value="{{ query }}" autofocus>
        <button type="submit">Buscar</button>
    </form>
</div>

{% if results %}
    {% if results.issues %}
    <div class="card">
        <h2>🐛 Issues ({{ results.issues|length }})</h2>
        {% for item in results.issues %}
        <div class="result-item">
            <h3>{{ item.title }} <span class="score">{{ item.score }}</span></h3>
            <div class="meta">
                <span class="badge badge-{{ item.metadata.status }}">{{ item.metadata.status }}</span>
                <span>Outcome: {{ item.metadata.outcome }}</span>
                <span>Owner: {{ item.metadata.owner }}</span>
            </div>
            <div class="content">{{ item.content }}</div>
        </div>
        {% endfor %}
    </div>
    {% endif %}
    
    {% if results.docs %}
    <div class="card">
        <h2>📚 Documentación ({{ results.docs|length }})</h2>
        {% for item in results.docs %}
        <div class="result-item">
            <h3>{{ item.title }} <span class="score">{{ item.score }}</span></h3>
            <div class="meta">
                <span class="badge badge-{{ item.metadata.chunk_type }}">{{ item.metadata.chunk_type }}</span>
                <span>Source: {{ item.metadata.doc_source }}</span>
                {% if item.metadata.verified %}✅ Verificado{% endif %}
            </div>
            <div class="content">{{ item.content }}</div>
        </div>
        {% endfor %}
    </div>
    {% endif %}
    
    {% if results.files %}
    <div class="card">
        <h2>📁 Archivos ({{ results.files|length }})</h2>
        {% for item in results.files %}
        <div class="result-item">
            <h3>{{ item.title }} <span class="score">{{ item.score }}</span></h3>
            <div class="meta">
                <span>Language: {{ item.metadata.language }}</span>
            </div>
            <div class="content">{{ item.content }}</div>
        </div>
        {% endfor %}
    </div>
    {% endif %}
    
    {% if results.reasoning %}
    <div class="card">
        <h2>💭 Razonamientos ({{ results.reasoning|length }})</h2>
        {% for item in results.reasoning %}
        <div class="result-item">
            <h3>{{ item.title }} <span class="score">{{ item.score }}</span></h3>
            <div class="meta">
                <span class="badge badge-{{ item.metadata.status }}">{{ item.metadata.status }}</span>
                <span>Owner: {{ item.metadata.owner }}</span>
            </div>
            <div class="content">{{ item.content }}</div>
        </div>
        {% endfor %}
    </div>
    {% endif %}
{% elif query %}
<div class="card">
    <p>No se encontraron resultados para "{{ query }}"</p>
</div>
{% endif %}
{% endblock %}'''
    
    # Template issues
    issues_template = '''{% extends "base.html" %}

{% block title %}Issues - GAVANTI KB{% endblock %}

{% block content %}
<div class="card">
    <h2>🐛 Gestión de Issues</h2>
    <div style="margin-bottom: 15px;">
        <a href="/issues" {% if not current_status %}style="font-weight: bold; color: #60a5fa;"{% endif %}>Todos</a> |
        <a href="/issues?status=raw" {% if current_status == 'raw' %}style="font-weight: bold; color: #60a5fa;"{% endif %}>Raw</a> |
        <a href="/issues?status=verified" {% if current_status == 'verified' %}style="font-weight: bold; color: #60a5fa;"{% endif %}>Verified</a> |
        <a href="/issues?status=merged" {% if current_status == 'merged' %}style="font-weight: bold; color: #60a5fa;"{% endif %}>Merged</a> |
        <a href="/issues?status=archived" {% if current_status == 'archived' %}style="font-weight: bold; color: #60a5fa;"{% endif %}>Archived</a>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Error</th>
                <th>Status</th>
                <th>Outcome</th>
                <th>Owner</th>
                <th>Created</th>
                <th>Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for issue in issues %}
            <tr>
                <td>#{{ issue.id }}</td>
                <td>{{ issue.error[:80] }}{% if issue.error|length > 80 %}...{% endif %}</td>
                <td><span class="badge badge-{{ issue.status }}">{{ issue.status }}</span></td>
                <td>{{ issue.outcome or 'N/A' }}</td>
                <td>{{ issue.owner }}</td>
                <td>{{ issue.created_at[:10] }}</td>
                <td class="actions">
                    {% if issue.status == 'raw' %}
                    <button class="btn btn-verify" onclick="updateStatus({{ issue.id }}, 'verified')">Verify</button>
                    {% endif %}
                    {% if issue.status != 'archived' %}
                    <button class="btn btn-archive" onclick="updateStatus({{ issue.id }}, 'archived')">Archive</button>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
{% endblock %}

{% block extra_js %}
<script>
async function updateStatus(issueId, status) {
    try {
        const response = await fetch(`/api/issues/${issueId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: status, verified_by: 'web-panel' })
        });
        
        if (response.ok) {
            location.reload();
        } else {
            alert('Error updating status');
        }
    } catch (e) {
        alert('Error: ' + e.message);
    }
}
</script>
{% endblock %}'''
    
    # Guardar templates
    (templates_dir / 'base.html').write_text(base_template, encoding='utf-8')
    (templates_dir / 'index.html').write_text(index_template, encoding='utf-8')
    (templates_dir / 'search.html').write_text(search_template, encoding='utf-8')
    (templates_dir / 'issues.html').write_text(issues_template, encoding='utf-8')
    
    print("✅ Templates HTML creados")


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='VELMA Knowledge Base Search & Panel')
    parser.add_argument('--web', '-w', action='store_true', help='Iniciar panel web')
    parser.add_argument('--host', default='127.0.0.1', help='Host para el servidor web')
    parser.add_argument('--port', '-p', type=int, default=5000, help='Puerto para el servidor web')
    parser.add_argument('--create-templates', '-t', action='store_true', help='Crear templates HTML')
    
    args, remaining = parser.parse_known_args()
    
    # Crear templates si se solicita
    if args.create_templates:
        create_templates()
        return 0
    
    # Modo web
    if args.web:
        print("="*60)
        print("  VELMA - Knowledge Base Web Panel (Fase 3)")
        print("="*60)
        print(f"\n🌐 Iniciando servidor en http://{args.host}:{args.port}")
        print("\nPresiona Ctrl+C para detener")
        print("-"*60)
        
        # Crear templates si no existen
        if not Path('templates').exists():
            create_templates()
        
        app.run(host=args.host, port=args.port, debug=True)
        return 0
    
    # Modo CLI - pasar a cli_search
    sys.argv = [sys.argv[0]] + remaining
    cli_search()
    return 0


if __name__ == "__main__":
    sys.exit(main())
