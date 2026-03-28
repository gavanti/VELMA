#!/usr/bin/env python3
"""
GAVANTI - Knowledge Base Indexer (Fase 2)
Indexa archivos del proyecto por hash, genera summaries, indexa documentación .md por chunks
"""

import os
import re
import sqlite3
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Importar utilidades locales
try:
    from kb_utils import (
        compute_hash, compute_file_hash, format_json_field,
        detect_chunk_type, get_chunk_weight,
        encode_text, encode_texts
    )
except ImportError:
    # Si no existe kb_utils, definir funciones básicas
    import hashlib
    import json
    
    def compute_hash(text: str) -> str:
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def compute_file_hash(content: bytes) -> str:
        return hashlib.md5(content).hexdigest()
    
    def format_json_field(data) -> str:
        return json.dumps(data, ensure_ascii=False)
    
    def detect_chunk_type(title: str, body: str) -> str:
        title_lower = title.lower()
        body_lower = body.lower()
        constraint_keywords = ['nunca', 'siempre', 'obligatorio', 'prohibido', 'exactamente', 'solo', 'único']
        if any(kw in title_lower or kw in body_lower for kw in constraint_keywords):
            return 'constraint'
        rule_keywords = ['regla', 'política', 'debe', 'requiere', 'acumula', 'canjea']
        if any(kw in title_lower or kw in body_lower for kw in rule_keywords):
            return 'rule'
        procedure_keywords = ['paso', 'cómo', 'para', 'seguir', 'proceso', 'registrar']
        if any(kw in title_lower or kw in body_lower for kw in procedure_keywords):
            return 'procedure'
        example_keywords = ['ejemplo', 'ilustración', 'caso', 'muestra']
        if any(kw in title_lower or kw in body_lower for kw in example_keywords):
            return 'example'
        return 'concept'
    
    def get_chunk_weight(chunk_type: str) -> int:
        weights = {'constraint': 10, 'rule': 8, 'procedure': 7, 'concept': 5, 'example': 3}
        return weights.get(chunk_type, 5)

    def encode_text(text: str) -> bytes:
        return None  # fallback sin sentence-transformers

    def encode_texts(texts: list) -> list:
        return [None] * len(texts)

# Configuración
DB_NAME = "knowledge.db"

# Extensiones de archivos soportados
CODE_EXTENSIONS = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.jsx': 'jsx',
    '.tsx': 'tsx',
    '.html': 'html',
    '.css': 'css',
    '.scss': 'scss',
    '.sql': 'sql',
    '.md': 'markdown',
    '.mdx': 'mdx',
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.toml': 'toml',
    '.sh': 'shell',
    '.bash': 'shell',
}

# Directorios a ignorar
IGNORE_DIRS = {
    '.git', '__pycache__', 'node_modules', '.venv', 'venv',
    'dist', 'build', '.next', '.cache', 'coverage',
    '.pytest_cache', '.mypy_cache', '.tox'
}

# Archivos a ignorar
IGNORE_FILES = {
    '.DS_Store', 'Thumbs.db', '.env', '.env.local',
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml',
    'knowledge.db', 'knowledge.db-journal'
}


class KnowledgeIndexer:
    """Indexador de conocimiento para el knowledge base"""
    
    def __init__(self, db_path: str = DB_NAME, project_path: str = "."):
        self.db_path = db_path
        self.project_path = Path(project_path).resolve()
        self.conn = None
        self.cursor = None
        self.stats = {
            'files_indexed': 0,
            'files_skipped': 0,
            'docs_indexed': 0,
            'chunks_created': 0,
            'functions_indexed': 0
        }
    
    def connect(self):
        """Conecta a la base de datos"""
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        return self
    
    def close(self):
        """Cierra la conexión a la base de datos"""
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # ============================================
    # Indexación de Archivos
    # ============================================
    
    def should_index_file(self, file_path: Path) -> bool:
        """Determina si un archivo debe ser indexado"""
        # Ignorar archivos específicos
        if file_path.name in IGNORE_FILES:
            return False
        
        # Ignorar directorios
        for part in file_path.parts:
            if part in IGNORE_DIRS:
                return False
        
        # Solo indexar extensiones conocidas
        if file_path.suffix not in CODE_EXTENSIONS:
            return False
        
        return True
    
    def detect_language(self, file_path: Path) -> str:
        """Detecta el lenguaje de un archivo"""
        return CODE_EXTENSIONS.get(file_path.suffix, 'unknown')
    
    def generate_file_summary(self, file_path: Path, content: str) -> str:
        """Genera un resumen simple de un archivo"""
        lines = content.split('\n')
        
        # Buscar docstring o comentario inicial
        summary = None
        for line in lines[:20]:
            line = line.strip()
            # Python docstring
            if line.startswith('"""') or line.startswith("'''"):
                # Extraer primera línea del docstring
                doc = line.strip('"\'')
                if doc:
                    summary = doc[:200]
                    break
            # Comentarios de una línea
            elif line.startswith('#') and len(line) > 3:
                summary = line[1:].strip()[:200]
                break
            # JS/TS comentarios
            elif line.startswith('//') and len(line) > 3:
                summary = line[2:].strip()[:200]
                break
            # JS/TS block comments
            elif line.startswith('/*') and len(line) > 4:
                summary = line[2:].strip('*/ ')[:200]
                break
        
        if not summary:
            # Generar resumen basado en el nombre y extensión
            lang = self.detect_language(file_path)
            summary = f"Archivo {lang}: {file_path.name}"
        
        return summary
    
    def extract_functions_python(self, content: str, file_path: Path) -> List[Dict]:
        """Extrae funciones de código Python"""
        functions = []
        
        # Patrón para funciones y métodos
        pattern = r'^(\s*)def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*([^:]+))?:\s*(?:"""([^"]*)""")?'
        
        for match in re.finditer(pattern, content, re.MULTILINE):
            indent, name, params, return_type, docstring = match.groups()
            
            # Calcular líneas
            start_pos = content[:match.start()].count('\n') + 1
            
            # Encontrar el final de la función (línea con mismo o menor indent)
            lines = content.split('\n')
            end_line = start_pos
            func_indent = len(indent)
            
            for i in range(start_pos, len(lines)):
                line = lines[i]
                if line.strip() and not line.startswith('#'):
                    line_indent = len(line) - len(line.lstrip())
                    if line_indent <= func_indent and i > start_pos:
                        break
                end_line = i + 1
            
            func_hash = compute_hash(f"{name}({params})")
            
            functions.append({
                'name': name,
                'signature': f"def {name}({params})" + (f" -> {return_type}" if return_type else ""),
                'docstring': docstring.strip() if docstring else "",
                'start_line': start_pos,
                'end_line': end_line,
                'hash': func_hash
            })
        
        return functions
    
    def extract_functions_js_ts(self, content: str, file_path: Path) -> List[Dict]:
        """Extrae funciones de código JavaScript/TypeScript"""
        functions = []
        
        # Patrones para diferentes tipos de funciones
        patterns = [
            # function name(params) { }
            r'function\s+(\w+)\s*\(([^)]*)\)\s*(?::\s*(\w+))?\s*\{',
            # const name = (params) => { }
            r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>',
            # method(params) { }
            r'(?:async\s+)?(\w+)\s*\(([^)]*)\)\s*(?::\s*(\w+))?\s*\{',
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                params = match.group(2)
                
                start_pos = content[:match.start()].count('\n') + 1
                
                # Encontrar el final de la función
                lines = content.split('\n')
                end_line = start_pos
                brace_count = 0
                found_open = False
                
                for i in range(start_pos - 1, len(lines)):
                    line = lines[i]
                    for char in line:
                        if char == '{':
                            brace_count += 1
                            found_open = True
                        elif char == '}':
                            brace_count -= 1
                    
                    if found_open and brace_count == 0:
                        end_line = i + 1
                        break
                    end_line = i + 1
                
                func_hash = compute_hash(f"{name}({params})")
                
                # Buscar JSDoc
                docstring = ""
                if start_pos > 1:
                    prev_lines = lines[max(0, start_pos-5):start_pos-1]
                    for prev_line in reversed(prev_lines):
                        if '*/' in prev_line:
                            break
                        if prev_line.strip().startswith('*'):
                            docstring = prev_line.strip().lstrip('*').strip() + " " + docstring
                
                functions.append({
                    'name': name,
                    'signature': f"{name}({params})",
                    'docstring': docstring.strip(),
                    'start_line': start_pos,
                    'end_line': end_line,
                    'hash': func_hash
                })
        
        return functions
    
    def index_file(self, file_path: Path) -> bool:
        """Indexa un archivo individual"""
        if not self.should_index_file(file_path):
            return False
        
        try:
            # Leer contenido
            with open(file_path, 'rb') as f:
                content_bytes = f.read()
            
            content = content_bytes.decode('utf-8', errors='ignore')
            file_hash = compute_file_hash(content_bytes)
            
            # Calcular ruta relativa
            rel_path = str(file_path.relative_to(self.project_path))
            
            # Verificar si el archivo ya está indexado y no ha cambiado
            self.cursor.execute(
                "SELECT hash FROM files_index WHERE path = ?",
                (rel_path,)
            )
            result = self.cursor.fetchone()
            
            if result and result[0] == file_hash:
                # Archivo no ha cambiado
                self.stats['files_skipped'] += 1
                return False
            
            # Generar resumen
            summary = self.generate_file_summary(file_path, content)
            language = self.detect_language(file_path)

            # Generar embedding del summary
            file_embedding = encode_text(summary) if summary else None

            # Insertar o actualizar en files_index
            self.cursor.execute("""
                INSERT OR REPLACE INTO files_index (path, hash, summary, language, computed_at)
                VALUES (?, ?, ?, ?, ?)
            """, (rel_path, file_hash, summary, language, datetime.now().isoformat()))

            # Guardar embedding en files_index (columna no existe en schema original
            # — usamos UPDATE separado para no romper el INSERT OR REPLACE)
            try:
                self.cursor.execute(
                    "UPDATE files_index SET embedding = ? WHERE path = ?",
                    (file_embedding, rel_path)
                )
            except Exception:
                pass  # La columna embedding puede no existir en DBs antiguas

            # Extraer y indexar funciones
            if language == 'python':
                functions = self.extract_functions_python(content, file_path)
            elif language in ('javascript', 'typescript', 'jsx', 'tsx'):
                functions = self.extract_functions_js_ts(content, file_path)
            else:
                functions = []

            # Generar embeddings de funciones en batch
            if functions:
                func_texts = [
                    f['docstring'][:200] if f['docstring'] else f"Función {f['name']}"
                    for f in functions
                ]
                func_embeddings = encode_texts(func_texts)
            else:
                func_embeddings = []

            # Eliminar funciones antiguas de este archivo
            self.cursor.execute(
                "DELETE FROM functions_index WHERE file_path = ?",
                (rel_path,)
            )

            # Insertar nuevas funciones
            for func, func_emb in zip(functions, func_embeddings):
                self.cursor.execute("""
                    INSERT INTO functions_index 
                    (file_path, function_name, signature, docstring, start_line, end_line, hash, summary, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    rel_path,
                    func['name'],
                    func['signature'],
                    func['docstring'],
                    func['start_line'],
                    func['end_line'],
                    func['hash'],
                    func['docstring'][:200] if func['docstring'] else f"Función {func['name']}",
                    func_emb
                ))
                self.stats['functions_indexed'] += 1
            
            self.stats['files_indexed'] += 1
            return True
            
        except Exception as e:
            print(f"  [WARN]  Error indexando {file_path}: {e}")
            return False
    
    def index_project_files(self, target_path: str = "."):
        """Indexa todos los archivos del proyecto"""
        target = self.project_path / target_path
        
        if target.is_file():
            if self.index_file(target):
                print(f"  [OK] {target.relative_to(self.project_path)}")
        elif target.is_dir():
            for file_path in target.rglob('*'):
                if file_path.is_file():
                    if self.index_file(file_path):
                        rel_path = file_path.relative_to(self.project_path)
                        print(f"  [OK] {rel_path}")
        
        self.conn.commit()
    
    # ============================================
    # Indexación de Documentación
    # ============================================
    
    def split_markdown_into_chunks(self, content: str, doc_source: str) -> List[Dict]:
        """Divide un documento markdown en chunks semánticos"""
        chunks = []
        lines = content.split('\n')
        
        current_chunk = {
            'title': '',
            'body': '',
            'order': 0
        }
        order = 0
        
        for line in lines:
            # Detectar headers
            header_match = re.match(r'^(#{1,6})\s+(.+)$', line)
            
            if header_match:
                # Guardar chunk anterior si tiene contenido
                if current_chunk['body'].strip():
                    chunks.append({
                        'title': current_chunk['title'] or 'Introducción',
                        'body': current_chunk['body'].strip(),
                        'order': current_chunk['order']
                    })
                
                # Iniciar nuevo chunk
                level = len(header_match.group(1))
                title = header_match.group(2).strip()
                
                current_chunk = {
                    'title': title,
                    'body': line + '\n',
                    'order': order
                }
                order += 1
            else:
                current_chunk['body'] += line + '\n'
        
        # Agregar último chunk
        if current_chunk['body'].strip():
            chunks.append({
                'title': current_chunk['title'] or 'Contenido',
                'body': current_chunk['body'].strip(),
                'order': current_chunk['order']
            })
        
        return chunks
    
    def index_documentation(self, doc_path: Path, applies_to: List[str] = None):
        """Indexa un archivo de documentación markdown"""
        if not doc_path.exists():
            print(f"  [WARN]  Documento no encontrado: {doc_path}")
            return
        
        try:
            with open(doc_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            doc_hash = compute_hash(content)
            doc_source = doc_path.name
            
            # Verificar si el documento ya está indexado
            self.cursor.execute(
                "SELECT hash FROM docs_index WHERE doc_source = ? LIMIT 1",
                (doc_source,)
            )
            result = self.cursor.fetchone()
            
            if result and result[0] == doc_hash:
                print(f"  [skip]  Documento sin cambios: {doc_source}")
                return
            
            # Eliminar chunks antiguos
            self.cursor.execute(
                "DELETE FROM docs_index WHERE doc_source = ?",
                (doc_source,)
            )
            
            # Dividir en chunks
            chunks = self.split_markdown_into_chunks(content, doc_source)

            # Generar embeddings en batch (título + cuerpo como texto de consulta)
            chunk_texts = [f"{c['title']} {c['body']}" for c in chunks]
            chunk_embeddings = encode_texts(chunk_texts)

            # Insertar chunks
            for chunk, chunk_emb in zip(chunks, chunk_embeddings):
                chunk_type = detect_chunk_type(chunk['title'], chunk['body'])
                chunk_hash = compute_hash(chunk['title'] + chunk['body'])

                self.cursor.execute("""
                    INSERT INTO docs_index 
                    (doc_source, chunk_title, chunk_body, chunk_type, order_in_doc, hash, verified, applies_to, updated_at, embedding)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    doc_source,
                    chunk['title'],
                    chunk['body'],
                    chunk_type,
                    chunk['order'],
                    chunk_hash,
                    0,  # No verificado por defecto
                    format_json_field(applies_to or ['chakana', 'repovg']),
                    datetime.now().isoformat(),
                    chunk_emb
                ))
                
                self.stats['chunks_created'] += 1
            
            self.stats['docs_indexed'] += 1
            print(f"  [OK] {doc_source}: {len(chunks)} chunks")
            
        except Exception as e:
            print(f"  [WARN]  Error indexando documentación {doc_path}: {e}")
    
    def index_all_docs(self, docs_dir: str = "docs"):
        """Indexa todos los documentos markdown en un directorio"""
        docs_path = self.project_path / docs_dir
        
        if not docs_path.exists():
            print(f"  [WARN]  Directorio de documentos no encontrado: {docs_path}")
            return
        
        for doc_file in docs_path.glob('*.md'):
            self.index_documentation(doc_file)
        
        self.conn.commit()
    
    # ============================================
    # Funciones de utilidad
    # ============================================
    
    def get_stats(self) -> Dict:
        """Retorna estadísticas de indexación"""
        return self.stats.copy()
    
    def print_stats(self):
        """Imprime estadísticas"""
        print("\n" + "="*50)
        print("ESTADÍSTICAS DE INDEXACIÓN")
        print("="*50)
        print(f"  Archivos indexados: {self.stats['files_indexed']}")
        print(f"  Archivos omitidos (sin cambios): {self.stats['files_skipped']}")
        print(f"  Documentos indexados: {self.stats['docs_indexed']}")
        print(f"  Chunks creados: {self.stats['chunks_created']}")
        print(f"  Funciones indexadas: {self.stats['functions_indexed']}")
        print("="*50)


def main():
    """Función principal del indexer"""
    parser = argparse.ArgumentParser(
        description='GAVANTI Knowledge Base Indexer - Indexa archivos y documentación'
    )
    parser.add_argument(
        '--project', '-p',
        default='.',
        help='Ruta del proyecto a indexar (default: .)'
    )
    parser.add_argument(
        '--files', '-f',
        action='store_true',
        help='Indexar archivos de código'
    )
    parser.add_argument(
        '--docs', '-d',
        action='store_true',
        help='Indexar documentación markdown'
    )
    parser.add_argument(
        '--docs-dir',
        default='docs',
        help='Directorio de documentación (default: docs)'
    )
    parser.add_argument(
        '--target', '-t',
        default='.',
        help='Target específico a indexar (archivo o directorio)'
    )
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Indexar todo (archivos y documentación)'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("  GAVANTI - Knowledge Base Indexer (Fase 2)")
    print("  Indexación de archivos y documentación")
    print("="*60)
    print()
    
    # Si no se especifica nada, indexar todo
    if not args.files and not args.docs and not args.all:
        args.all = True
    
    if args.all:
        args.files = True
        args.docs = True
    
    with KnowledgeIndexer(project_path=args.project) as indexer:
        # Indexar archivos
        if args.files:
            print("[*] Indexando archivos de codigo...")
            indexer.index_project_files(args.target)
            print()

        # Indexar documentación
        if args.docs:
            print("[*] Indexando documentacion (con embeddings)...")
            indexer.index_all_docs(args.docs_dir)
            print()

        # Mostrar estadísticas
        indexer.print_stats()

    print("\n[OK] Indexacion completada")
    return 0


if __name__ == "__main__":
    sys.exit(main())
