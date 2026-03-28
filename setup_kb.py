#!/usr/bin/env python3
"""
VELMA - Knowledge Base Setup (Fase 1)
Crea knowledge.db con todas las tablas, FTS5, y prepara para embeddings
"""

import os
import sqlite3
import sys
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

# Configuraci n
try:
    from kb_utils import compute_hash, get_db_path
    DB_NAME = get_db_path()
except ImportError:
    DB_NAME = str(Path(__file__).parent / "knowledge.db")
MODEL_NAME = "all-MiniLM-L6-v2"
MODEL_PATH = Path("./models")

def get_db_version():
    """Obtiene la versi n de SQLite"""
    conn = sqlite3.connect(":memory:")
    version = conn.execute("SELECT sqlite_version()").fetchone()[0]
    conn.close()
    return version

def check_sqlite_features():
    """Verifica caracter sticas disponibles de SQLite"""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    
    features = {}
    
    # Verificar FTS5
    try:
        cursor.execute("CREATE VIRTUAL TABLE test_fts USING fts5(content);")
        cursor.execute("DROP TABLE test_fts;")
        features['fts5'] = True
    except:
        features['fts5'] = False
    
    # Verificar JSON1
    try:
        cursor.execute("SELECT json('{}');")
        features['json1'] = True
    except:
        features['json1'] = False
    
    conn.close()
    return features

def create_database():
    """Crea o actualiza la base de datos SQLite con todas las tablas"""
    db_path = Path(DB_NAME)
    
    is_new = not db_path.exists()
    if is_new:
        print(f"[db] Creando base de datos: {DB_NAME}")
    else:
        print(f"[db] Verificando/Actualizando base de datos existente: {DB_NAME}")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    
    # ============================================
    # TABLA: issues_log - errores y resoluciones
    # ============================================
    print("  [task] Creando tabla issues_log...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issues_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            error TEXT NOT NULL,
            resolution TEXT,
            context TEXT,
            approach TEXT,
            attempts TEXT,  -- JSON
            tags TEXT,  -- JSON
            outcome TEXT CHECK(outcome IN ('unverified', 'success', 'failed', 'human_confirmed')) DEFAULT 'unverified',
            evidence TEXT,
            status TEXT CHECK(status IN ('raw', 'verified', 'merged', 'archived')) DEFAULT 'raw',
            fingerprint TEXT UNIQUE,
            embedding BLOB,  -- Vector de 384 dimensiones (almacenado como bytes)
            verified_by TEXT,
            shared_id INTEGER,
            owner TEXT NOT NULL DEFAULT 'unknown',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            verified_at DATETIME,
            expires_at DATETIME DEFAULT (datetime('now', '+90 days'))
        );
    """)
    
    #  ndice FTS5 para issues_log
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS issues_log_fts USING fts5(
            error, resolution, context, approach, tags,
            content='issues_log',
            content_rowid='id'
        );
    """)
    
    # Triggers para mantener FTS5 sincronizado
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS issues_log_fts_insert AFTER INSERT ON issues_log BEGIN
            INSERT INTO issues_log_fts(rowid, error, resolution, context, approach, tags)
            VALUES (new.id, new.error, new.resolution, new.context, new.approach, new.tags);
        END;
    """)
    
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS issues_log_fts_update AFTER UPDATE ON issues_log BEGIN
            INSERT INTO issues_log_fts(issues_log_fts, rowid, error, resolution, context, approach, tags)
            VALUES ('delete', old.id, old.error, old.resolution, old.context, old.approach, old.tags);
            INSERT INTO issues_log_fts(rowid, error, resolution, context, approach, tags)
            VALUES (new.id, new.error, new.resolution, new.context, new.approach, new.tags);
        END;
    """)
    
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS issues_log_fts_delete AFTER DELETE ON issues_log BEGIN
            INSERT INTO issues_log_fts(issues_log_fts, rowid, error, resolution, context, approach, tags)
            VALUES ('delete', old.id, old.error, old.resolution, old.context, old.approach, old.tags);
        END;
    """)
    
    # ============================================
    # TABLA: docs_index - documentaci n y reglas
    # ============================================
    print("  [DOCS] Creando tabla docs_index...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS docs_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_source TEXT NOT NULL,
            chunk_title TEXT NOT NULL,
            chunk_body TEXT NOT NULL,
            chunk_type TEXT CHECK(chunk_type IN ('constraint', 'rule', 'procedure', 'concept', 'example')) DEFAULT 'concept',
            order_in_doc INTEGER,
            embedding BLOB,  -- Vector para b squeda sem ntica
            hash TEXT,
            verified BOOLEAN DEFAULT 0,
            applies_to TEXT,  -- JSON
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    #  ndice FTS5 para docs_index
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS docs_index_fts USING fts5(
            chunk_title, chunk_body,
            content='docs_index',
            content_rowid='id'
        );
    """)
    
    # Triggers para docs_index FTS5
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS docs_index_fts_insert AFTER INSERT ON docs_index BEGIN
            INSERT INTO docs_index_fts(rowid, chunk_title, chunk_body)
            VALUES (new.id, new.chunk_title, new.chunk_body);
        END;
    """)
    
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS docs_index_fts_update AFTER UPDATE ON docs_index BEGIN
            INSERT INTO docs_index_fts(docs_index_fts, rowid, chunk_title, chunk_body)
            VALUES ('delete', old.id, old.chunk_title, old.chunk_body);
            INSERT INTO docs_index_fts(rowid, chunk_title, chunk_body)
            VALUES (new.id, new.chunk_title, new.chunk_body);
        END;
    """)
    
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS docs_index_fts_delete AFTER DELETE ON docs_index BEGIN
            INSERT INTO docs_index_fts(docs_index_fts, rowid, chunk_title, chunk_body)
            VALUES ('delete', old.id, old.chunk_title, old.chunk_body);
        END;
    """)
    
    # ============================================
    # TABLA: files_index - archivos procesados
    # ============================================
    print("  [FILES] Creando tabla files_index...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS files_index (
            path TEXT PRIMARY KEY,
            hash TEXT NOT NULL,
            summary TEXT,
            language TEXT,
            computed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    #  ndice FTS5 para files_index
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS files_index_fts USING fts5(
            path, summary,
            content='files_index',
            content_rowid='rowid'
        );
    """)
    
    # Triggers para files_index FTS5
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS files_index_fts_insert AFTER INSERT ON files_index BEGIN
            INSERT INTO files_index_fts(rowid, path, summary)
            VALUES (new.rowid, new.path, new.summary);
        END;
    """)
    
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS files_index_fts_update AFTER UPDATE ON files_index BEGIN
            INSERT INTO files_index_fts(files_index_fts, rowid, path, summary)
            VALUES ('delete', old.rowid, old.path, old.summary);
            INSERT INTO files_index_fts(rowid, path, summary)
            VALUES (new.rowid, new.path, new.summary);
        END;
    """)
    
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS files_index_fts_delete AFTER DELETE ON files_index BEGIN
            INSERT INTO files_index_fts(files_index_fts, rowid, path, summary)
            VALUES ('delete', old.rowid, old.path, old.summary);
        END;
    """)
    
    # ============================================
    # TABLA: functions_index - funciones/procedimientos
    # ============================================
    print("  [CONFIG]  Creando tabla functions_index...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS functions_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            function_name TEXT NOT NULL,
            signature TEXT,
            docstring TEXT,
            start_line INTEGER,
            end_line INTEGER,
            hash TEXT NOT NULL,
            summary TEXT,
            embedding BLOB,
            computed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (file_path) REFERENCES files_index(path)
        );
    """)
    
    # ============================================
    # TABLA: reasoning_log - razonamientos del agente
    # ============================================
    print("    Creando tabla reasoning_log...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reasoning_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            approach TEXT NOT NULL,
            outcome TEXT,
            linked_issue_id INTEGER,
            status TEXT CHECK(status IN ('raw', 'verified', 'merged')) DEFAULT 'raw',
            owner TEXT NOT NULL DEFAULT 'unknown',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (linked_issue_id) REFERENCES issues_log(id)
        );
    """)
    
    #  ndice FTS5 para reasoning_log
    cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS reasoning_log_fts USING fts5(
            task, approach, outcome,
            content='reasoning_log',
            content_rowid='id'
        );
    """)
    
    # Triggers para reasoning_log FTS5
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS reasoning_log_fts_insert AFTER INSERT ON reasoning_log BEGIN
            INSERT INTO reasoning_log_fts(rowid, task, approach, outcome)
            VALUES (new.id, new.task, new.approach, new.outcome);
        END;
    """)
    
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS reasoning_log_fts_update AFTER UPDATE ON reasoning_log BEGIN
            INSERT INTO reasoning_log_fts(reasoning_log_fts, rowid, task, approach, outcome)
            VALUES ('delete', old.id, old.task, old.approach, old.outcome);
            INSERT INTO reasoning_log_fts(rowid, task, approach, outcome)
            VALUES (new.id, new.task, new.approach, new.outcome);
        END;
    """)
    
    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS reasoning_log_fts_delete AFTER DELETE ON reasoning_log BEGIN
            INSERT INTO reasoning_log_fts(reasoning_log_fts, rowid, task, approach, outcome)
            VALUES ('delete', old.id, old.task, old.approach, old.outcome);
        END;
    """)
    
    # ============================================
    # TABLA: schemas_index - esquemas de base de datos
    # ============================================
    print("      Creando tabla schemas_index...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schemas_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            schema_definition TEXT NOT NULL,
            description TEXT,
            embedding BLOB,
            hash TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
    """)
    
    # ============================================
    # TABLA: session_metadata - metadatos de sesiones
    # ============================================
    print("    Creando tabla session_metadata...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT UNIQUE NOT NULL,
            owner TEXT NOT NULL,
            start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            end_time DATETIME,
            summary TEXT,
            files_touched TEXT,  -- JSON
            issues_created INTEGER DEFAULT 0,
            issues_resolved INTEGER DEFAULT 0
        );
    """)
    
    # ============================================
    # TABLA: shared_chunks - chunks compartidos (sync)
    # ============================================
    print("    Creando tabla shared_chunks...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS shared_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chunk_type TEXT NOT NULL,  -- 'issue', 'doc', 'reasoning', 'schema'
            source_table TEXT NOT NULL,
            source_id INTEGER NOT NULL,
            content_hash TEXT NOT NULL,
            content_json TEXT NOT NULL,
            merged_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            merged_by TEXT NOT NULL
        );
    """)
    
    # ============================================
    #  ndices adicionales para performance
    # ============================================
    print("    Creando  ndices...")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_status ON issues_log(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_owner ON issues_log(owner);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_fingerprint ON issues_log(fingerprint);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_created ON issues_log(created_at);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_issues_expires ON issues_log(expires_at);")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_source ON docs_index(doc_source);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_type ON docs_index(chunk_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_verified ON docs_index(verified);")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_hash ON files_index(hash);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_language ON files_index(language);")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_functions_file ON functions_index(file_path);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_functions_name ON functions_index(function_name);")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reasoning_status ON reasoning_log(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reasoning_owner ON reasoning_log(owner);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_reasoning_issue ON reasoning_log(linked_issue_id);")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shared_type ON shared_chunks(chunk_type);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shared_hash ON shared_chunks(content_hash);")
    
    conn.commit()
    conn.close()
    
    print(f"[OK] Base de datos creada exitosamente: {DB_NAME}")
    return True

def create_config_file():
    """Crea archivo de configuraci n .env.example"""
    config_content = """# VELMA Knowledge Base Configuration

# Base de datos
DB_PATH=knowledge.db

# Modelo de embeddings (opcional - para b squeda sem ntica avanzada)
MODEL_NAME=all-MiniLM-L6-v2
MODEL_PATH=./models

# Configuraci n de sync (Fase 4)
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_TABLE=shared_knowledge

# Configuraci n de expiraci n
DEFAULT_EXPIRY_DAYS=90
MIN_CONFIDENCE_SCORE=0.75
VECTOR_SIMILARITY_THRESHOLD=0.85

# GitHub (para GitHub Actions)
GITHUB_TOKEN=
REPO_OWNER=
REPO_NAME=

# Configuraci n del dev
DEV_NAME=developer
PROJECT_NAME=my_project
"""
    
    with open(".env.example", "w") as f:
        f.write(config_content)
    
    print("[OK] Archivo .env.example creado")

def create_requirements():
    """Crea archivo requirements.txt"""
    requirements = """# Core dependencies
numpy>=1.24.0
python-dotenv>=1.0.0

# Optional: For semantic search with local embeddings
# sentence-transformers>=2.2.0

# Optional: For file watching
# watchdog>=3.0.0

# Web panel (Fase 3)
flask>=2.3.0

# Optional: Vector search extension
# sqlite-vec>=0.1.0
"""
    
    with open("requirements.txt", "w") as f:
        f.write(requirements)
    
    print("[OK] Archivo requirements.txt creado")

def create_utils_module():
    """Crea m dulo de utilidades para el knowledge base"""
    utils_code = '''"""
VELMA - Knowledge Base Utilities
Funciones auxiliares para el sistema de knowledge base
"""

import hashlib
import json
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta

def get_db_path():
    """Retorna la ruta absoluta a la base de datos knowledge.db"""
    return str(Path(__file__).parent / "knowledge.db")

def compute_hash(text: str) -> str:
    """Calcula hash MD5 de un texto"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def compute_file_hash(content: bytes) -> str:
    """Calcula hash MD5 del contenido de un archivo"""
    return hashlib.md5(content).hexdigest()

def parse_json_field(field_value) -> any:
    """Parsea un campo JSON de la base de datos"""
    if not field_value:
        return []
    try:
        return json.loads(field_value)
    except:
        return []

def format_json_field(data) -> str:
    """Formatea datos para almacenar como JSON"""
    return json.dumps(data, ensure_ascii=False)

def get_expiry_date(days: int = 90) -> str:
    """Calcula fecha de expiracion"""
    expiry = datetime.now() + timedelta(days=days)
    return expiry.isoformat()

def detect_chunk_type(title: str, body: str) -> str:
    """Detecta automaticamente el tipo de chunk basado en contenido"""
    title_lower = title.lower()
    body_lower = body.lower()
    
    constraint_keywords = ['nunca', 'siempre', 'obligatorio', 'prohibido', 'exactamente', 'solo', 'unico']
    if any(kw in title_lower or kw in body_lower for kw in constraint_keywords):
        return 'constraint'
    
    rule_keywords = ['regla', 'politica', 'debe', 'requiere', 'acumula', 'canjea']
    if any(kw in title_lower or kw in body_lower for kw in rule_keywords):
        return 'rule'
    
    procedure_keywords = ['paso', 'como', 'para', 'seguir', 'proceso', 'registrar']
    if any(kw in title_lower or kw in body_lower for kw in procedure_keywords):
        return 'procedure'
    
    example_keywords = ['ejemplo', 'ilustracion', 'caso', 'muestra']
    if any(kw in title_lower or kw in body_lower for kw in example_keywords):
        return 'example'
    
    return 'concept'

def get_chunk_weight(chunk_type: str) -> int:
    """Retorna el peso de un tipo de chunk para ranking"""
    weights = {'constraint': 10, 'rule': 8, 'procedure': 7, 'concept': 5, 'example': 3}
    return weights.get(chunk_type, 5)

def cosine_similarity(vec1, vec2):
    """Calcula similitud coseno entre dos vectores float32"""
    if vec1 is None or vec2 is None:
        return 0.0
    try:
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

# ============================================================
# Embedding Model (singleton multilingue profesional)
# ============================================================

_embedding_model = None

def get_embedding_model():
    """Retorna el modelo multilingue como singleton."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _embedding_model

def encode_text(text: str) -> bytes:
    """Genera embedding BLOB para un texto"""
    if not text: return None
    model = get_embedding_model()
    vec = model.encode(text, convert_to_numpy=True)
    return vec.astype(np.float32).tobytes()

def encode_texts(texts: list) -> list:
    """Genera embeddings en batch"""
    if not texts: return []
    model = get_embedding_model()
    vecs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return [v.astype(np.float32).tobytes() for v in vecs]

# ============================================================
# Ollama Enricher (Traduccion y Enriquecimiento Opcional)
# ============================================================

class OllamaEnricher:
    """Usa Ollama local para traducir y enriquecer textos tecnicos."""
    def __init__(self, model="llama3.2:1b"):
        self.model = model
        self.available = False
        try:
            import ollama
            ollama.list()
            self.available = True
        except:
            self.available = False

    def translate_and_enrich(self, text: str) -> str:
        """Genera version bilingue del texto si Ollama esta disponible."""
        if not self.available or not text:
            return text
        import ollama
        prompt = f"Translate and enrich this technical text between Spanish and English. Output only the consolidated bilingual result:\\n{text}"
        try:
            response = ollama.generate(model=self.model, prompt=prompt)
            return f"{text}\\n\\n{response['response'].strip()}"
        except:
            return text
'''
    
    with open("kb_utils.py", "w") as f:
        f.write(utils_code)
    
    print("[OK] M dulo kb_utils.py creado")

def verify_setup():
    """Verifica que todo est  configurado correctamente"""
    print("\\n" + "="*50)
    print("VERIFICACI N DEL SETUP")
    print("="*50)
    
    # Versi n de SQLite
    sqlite_version = get_db_version()
    print(f"\\n[db] SQLite versi n: {sqlite_version}")
    
    # Caracter sticas disponibles
    features = check_sqlite_features()
    print(f"[SEARCH] Caracter sticas:")
    for feat, available in features.items():
        status = "[OK]" if available else "[ERR]"
        print(f"   {status} {feat}")
    
    # Verificar base de datos
    if Path(DB_NAME).exists():
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # Listar tablas
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
        tables = cursor.fetchall()
        print(f"\\n  Tablas creadas ({len(tables)}):")
        for table in tables:
            print(f"     {table[0]}")
        
        # Contar registros en tablas principales
        print(f"\\n  Estado inicial:")
        for table_name in ['issues_log', 'docs_index', 'files_index', 'reasoning_log']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                print(f"   {table_name}: {count} registros")
            except:
                pass
        
        conn.close()
    else:
        print("[ERR] Base de datos no encontrada")
        return False
    
    print("\\n" + "="*50)
    print("[OK] SETUP COMPLETADO EXITOSAMENTE")
    print("="*50)
    return True

def main():
    """Funci n principal de setup"""
    print("="*60)
    print("  VELMA - Knowledge Base Setup (Fase 1)")
    print("  Sistema de Memoria Persistente para Agentes de IA")
    print("="*60)
    print()
    
    # 1. Crear base de datos
    try:
        create_database()
    except Exception as e:
        print(f"[ERR] Error creando base de datos: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    # 2. Crear archivos de configuraci n
    create_config_file()
    create_requirements()
    create_utils_module()
    
    # 3. Verificaci n final
    verify_setup()
    
    print("\\n[task] Pr ximos pasos:")
    print("   1. Copia .env.example a .env y configura tus variables")
    print("   2. Instala dependencias: pip install -r requirements.txt")
    print("   3. Ejecuta Fase 2: python indexer.py")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
