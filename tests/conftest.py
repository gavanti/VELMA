"""
VELMA - Fixtures de pytest compartidos
DB en memoria, datos sintéticos listos para cada test
"""

import sys
import os
import sqlite3
import json
import hashlib
import pytest
from pathlib import Path
from datetime import datetime, timedelta

# Asegurar que el directorio raíz esté en el path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


# ============================================================
# Helpers internos
# ============================================================

def _apply_schema(conn: sqlite3.Connection):
    """Aplica el schema completo de VELMA a una conexión SQLite."""
    conn.execute("PRAGMA foreign_keys = ON;")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS issues_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            error TEXT NOT NULL,
            resolution TEXT,
            context TEXT,
            approach TEXT,
            attempts TEXT,
            tags TEXT,
            outcome TEXT CHECK(outcome IN ('unverified','success','failed','human_confirmed')) DEFAULT 'unverified',
            evidence TEXT,
            status TEXT CHECK(status IN ('raw','verified','merged','archived')) DEFAULT 'raw',
            fingerprint TEXT UNIQUE,
            embedding BLOB,
            verified_by TEXT,
            shared_id INTEGER,
            owner TEXT NOT NULL DEFAULT 'unknown',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            verified_at DATETIME,
            expires_at DATETIME DEFAULT (datetime('now', '+90 days'))
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS issues_log_fts USING fts5(
            error, resolution, context, approach, tags,
            content='issues_log',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS issues_log_fts_insert AFTER INSERT ON issues_log BEGIN
            INSERT INTO issues_log_fts(rowid, error, resolution, context, approach, tags)
            VALUES (new.id, new.error, new.resolution, new.context, new.approach, new.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS issues_log_fts_update AFTER UPDATE ON issues_log BEGIN
            INSERT INTO issues_log_fts(issues_log_fts, rowid, error, resolution, context, approach, tags)
            VALUES ('delete', old.id, old.error, old.resolution, old.context, old.approach, old.tags);
            INSERT INTO issues_log_fts(rowid, error, resolution, context, approach, tags)
            VALUES (new.id, new.error, new.resolution, new.context, new.approach, new.tags);
        END;

        CREATE TRIGGER IF NOT EXISTS issues_log_fts_delete AFTER DELETE ON issues_log BEGIN
            INSERT INTO issues_log_fts(issues_log_fts, rowid, error, resolution, context, approach, tags)
            VALUES ('delete', old.id, old.error, old.resolution, old.context, old.approach, old.tags);
        END;

        CREATE TABLE IF NOT EXISTS docs_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_source TEXT NOT NULL,
            chunk_title TEXT NOT NULL,
            chunk_body TEXT NOT NULL,
            chunk_type TEXT CHECK(chunk_type IN ('constraint','rule','procedure','concept','example')) DEFAULT 'concept',
            order_in_doc INTEGER,
            embedding BLOB,
            hash TEXT,
            verified BOOLEAN DEFAULT 0,
            applies_to TEXT,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS docs_index_fts USING fts5(
            chunk_title, chunk_body,
            content='docs_index',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS docs_index_fts_insert AFTER INSERT ON docs_index BEGIN
            INSERT INTO docs_index_fts(rowid, chunk_title, chunk_body)
            VALUES (new.id, new.chunk_title, new.chunk_body);
        END;

        CREATE TRIGGER IF NOT EXISTS docs_index_fts_update AFTER UPDATE ON docs_index BEGIN
            INSERT INTO docs_index_fts(docs_index_fts, rowid, chunk_title, chunk_body)
            VALUES ('delete', old.id, old.chunk_title, old.chunk_body);
            INSERT INTO docs_index_fts(rowid, chunk_title, chunk_body)
            VALUES (new.id, new.chunk_title, new.chunk_body);
        END;

        CREATE TRIGGER IF NOT EXISTS docs_index_fts_delete AFTER DELETE ON docs_index BEGIN
            INSERT INTO docs_index_fts(docs_index_fts, rowid, chunk_title, chunk_body)
            VALUES ('delete', old.id, old.chunk_title, old.chunk_body);
        END;

        CREATE TABLE IF NOT EXISTS files_index (
            path TEXT PRIMARY KEY,
            hash TEXT NOT NULL,
            summary TEXT,
            language TEXT,
            computed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS files_index_fts USING fts5(
            path, summary,
            content='files_index',
            content_rowid='rowid'
        );

        CREATE TRIGGER IF NOT EXISTS files_index_fts_insert AFTER INSERT ON files_index BEGIN
            INSERT INTO files_index_fts(rowid, path, summary)
            VALUES (new.rowid, new.path, new.summary);
        END;

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
            computed_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS reasoning_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            approach TEXT NOT NULL,
            outcome TEXT,
            linked_issue_id INTEGER,
            status TEXT CHECK(status IN ('raw','verified','merged')) DEFAULT 'raw',
            owner TEXT NOT NULL DEFAULT 'unknown',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS reasoning_log_fts USING fts5(
            task, approach, outcome,
            content='reasoning_log',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS reasoning_log_fts_insert AFTER INSERT ON reasoning_log BEGIN
            INSERT INTO reasoning_log_fts(rowid, task, approach, outcome)
            VALUES (new.id, new.task, new.approach, new.outcome);
        END;
    """)
    conn.commit()


def _make_fingerprint(error: str, resolution: str = "") -> str:
    return hashlib.md5(f"{error}|{resolution}".encode()).hexdigest()


# ============================================================
# Fixtures de base de datos
# ============================================================

@pytest.fixture
def db_conn():
    """Conexión SQLite en memoria con schema completo. Se descarta al terminar el test."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    _apply_schema(conn)
    yield conn
    conn.close()


@pytest.fixture
def db_conn_with_data(db_conn):
    """DB en memoria pre-poblada con datos sintéticos representativos."""
    from tests.fixtures.generate_test_data import populate_db
    populate_db(db_conn)
    yield db_conn


@pytest.fixture
def search_engine(db_conn_with_data, tmp_path):
    """
    Instancia de KnowledgeSearch apuntando a una DB de archivo temporal
    (necesaria porque KnowledgeSearch abre la DB por path, no por conexión).
    """
    from tests.fixtures.generate_test_data import populate_db
    from search import KnowledgeSearch

    db_file = tmp_path / "test_knowledge.db"
    conn = sqlite3.connect(str(db_file))
    conn.row_factory = sqlite3.Row
    _apply_schema(conn)
    populate_db(conn)
    conn.close()

    engine = KnowledgeSearch(str(db_file))
    engine.connect()
    yield engine
    engine.close()


@pytest.fixture
def merger_dbs(tmp_path):
    """
    Par de DBs temporales (local + shared) para tests de merge.
    Retorna (local_path, shared_path).
    """
    from tests.fixtures.generate_test_data import populate_db

    local_path = tmp_path / "local.db"
    shared_path = tmp_path / "shared.db"

    # Crear y poblar la DB local
    conn = sqlite3.connect(str(local_path))
    conn.row_factory = sqlite3.Row
    _apply_schema(conn)
    populate_db(conn)
    conn.close()

    # La shared se crea vacía; KnowledgeMerger aplica su propio schema
    sqlite3.connect(str(shared_path)).close()

    yield str(local_path), str(shared_path)


# ============================================================
# Fixtures de datos individuales
# ============================================================

@pytest.fixture
def sample_issue():
    """Issue de prueba individual con todos los campos."""
    return {
        "error": "Connection refused to Supabase on port 5432",
        "resolution": "Add exponential backoff retry (max 3 attempts)",
        "context": "src/payments.py:process_redeem()",
        "approach": "Timeout ocurría en conexiones lentas. Retry con backoff resuelve.",
        "attempts": json.dumps(["Intento 1: verificar credenciales - falló"]),
        "tags": json.dumps(["supabase", "connection", "retry"]),
        "outcome": "success",
        "evidence": "test_payments_retry PASSED (3/3)",
        "status": "verified",
        "owner": "dev1",
    }


@pytest.fixture
def sample_doc():
    """Chunk de documentación de prueba."""
    return {
        "doc_source": "chakana-reglas.md",
        "chunk_title": "Constraint: Valor del Aurio",
        "chunk_body": "El Aurio vale exactamente $0.01 USD. Nunca aplicar márgenes.",
        "chunk_type": "constraint",
        "order_in_doc": 0,
        "verified": 1,
        "applies_to": json.dumps(["chakana"]),
    }
