"""
VELMA - Generador de datos sintéticos para testing
Produce issues, docs y archivos de código realistas y reproducibles.
"""

import json
import hashlib
import random
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict

# Semilla fija para reproducibilidad
random.seed(42)

# ============================================================
# Templates de issues
# ============================================================

_ISSUE_TEMPLATES = [
    {
        "error": "Connection refused to {service} on port {port}",
        "resolution": "Add exponential backoff retry (max {retries} attempts)",
        "context": "{file}:{line}",
        "approach": "Timeout en conexiones lentas. Retry con backoff resuelve.",
        "tags": ["connection", "{service_tag}", "retry"],
        "outcome": "success",
        "evidence": "test_connection_retry PASSED (3/3)",
    },
    {
        "error": "Timeout on API call to {endpoint} after {seconds}s",
        "resolution": "Increase timeout to {new_seconds}s and add circuit breaker",
        "context": "{file}:{line}",
        "approach": "El endpoint es lento en horas pico. Timeout más alto + circuit breaker.",
        "tags": ["timeout", "api", "{service_tag}"],
        "outcome": "success",
        "evidence": "curl {endpoint}: 200 OK in 2.3s",
    },
    {
        "error": "RLS policy violation on table {table} for user {role}",
        "resolution": "Add policy: CREATE POLICY {table}_read ON {table} FOR SELECT USING (auth.uid() = user_id)",
        "context": "{file}:{line}",
        "approach": "Faltaba política RLS para el rol específico.",
        "tags": ["supabase", "rls", "auth"],
        "outcome": "success",
        "evidence": "test_rls_policy PASSED",
    },
    {
        "error": "JWT token expired for user session",
        "resolution": "Implement silent token refresh before expiry (refresh at 80% of TTL)",
        "context": "{file}:{line}",
        "approach": "Tokens expiraban en medio de operaciones largas.",
        "tags": ["auth", "jwt", "token"],
        "outcome": "success",
        "evidence": "test_token_refresh PASSED (5/5)",
    },
    {
        "error": "Aurio balance calculation returns negative value for user {user_id}",
        "resolution": "Add non-negative constraint check before UPDATE and rollback on violation",
        "context": "{file}:{line}",
        "approach": "Race condition entre dos transacciones simultáneas. Constraint + rollback.",
        "tags": ["aurios", "balance", "race-condition"],
        "outcome": "success",
        "evidence": "test_balance_negative PASSED (10/10 concurrent)",
    },
    {
        "error": "Foreign key constraint failed on missions.embajador_id",
        "resolution": "Verify embajador exists before INSERT, wrap in transaction",
        "context": "{file}:{line}",
        "approach": "INSERT sin verificar existencia del embajador.",
        "tags": ["database", "fk", "missions"],
        "outcome": "success",
        "evidence": "test_mission_fk PASSED",
    },
    {
        "error": "Flask server returns 500 on /api/v1/canjes endpoint",
        "resolution": "Fix missing null check on embajador.saldo before comparison",
        "context": "{file}:{line}",
        "approach": "saldo podía ser NULL para embajadores recién registrados.",
        "tags": ["flask", "api", "canjes", "null"],
        "outcome": "success",
        "evidence": "test_canjes_endpoint PASSED",
    },
    {
        "error": "Indexer skips files with unicode characters in path",
        "resolution": "Use pathlib.Path with encoding='utf-8' instead of os.path",
        "context": "{file}:{line}",
        "approach": "os.path fallaba con rutas que tenían tildes o ñ.",
        "tags": ["indexer", "unicode", "pathlib"],
        "outcome": "success",
        "evidence": "test_unicode_paths PASSED (12 test paths)",
    },
    {
        "error": "FTS5 MATCH throws OperationalError for query with special characters",
        "resolution": "Sanitize query: wrap each term in double quotes before passing to MATCH",
        "context": "{file}:{line}",
        "approach": "FTS5 interpreta : * \" AND OR como operadores. Necesita escape.",
        "tags": ["fts5", "search", "sanitization"],
        "outcome": "success",
        "evidence": 'test_fts5_special_chars PASSED (20 edge cases)',
    },
    {
        "error": "Merge deduplication creates false conflict for semantically identical issues",
        "resolution": "Lower SIMILARITY_ENRICH threshold from 0.95 to 0.92 for text similarity",
        "context": "{file}:{line}",
        "approach": "Jaccard similarity era muy estricto. Bajar threshold reduce falsos conflictos.",
        "tags": ["merge", "deduplication", "similarity"],
        "outcome": "success",
        "evidence": "test_merge_dedup PASSED (0 false conflicts in 50 test pairs)",
    },
]

_SERVICES = ["Supabase", "PostgreSQL", "Redis", "S3", "SendGrid"]
_SERVICE_TAGS = ["supabase", "postgresql", "redis", "s3", "email"]
_ENDPOINTS = ["/api/v1/canjes", "/api/v1/misiones", "/api/v1/embajadores", "/api/v1/tambus"]
_FILES = [
    "src/payments.py", "src/auth.py", "src/missions.py",
    "src/users.py", "search.py", "indexer.py", "merge_knowledge.py",
]
_TABLES = ["embajadores", "misiones", "aurios", "canjes", "tambus"]
_ROLES = ["embajador", "tambu_admin", "anonymous", "service_role"]
_STATUSES = ["raw", "verified", "verified", "verified", "merged"]  # mayoría verified


def _render_template(tpl: Dict, idx: int) -> Dict:
    """Rellena un template con valores concretos."""
    rng = random.Random(idx)
    svc_i = rng.randint(0, len(_SERVICES) - 1)
    rendered = {
        "error": tpl["error"].format(
            service=_SERVICES[svc_i],
            service_tag=_SERVICE_TAGS[svc_i],
            port=rng.choice([5432, 6379, 443, 587]),
            endpoint=rng.choice(_ENDPOINTS),
            seconds=rng.choice([10, 15, 30]),
            new_seconds=rng.choice([60, 90, 120]),
            table=rng.choice(_TABLES),
            role=rng.choice(_ROLES),
            user_id=f"usr_{rng.randint(100, 999)}",
            file=rng.choice(_FILES),
            line=rng.randint(10, 500),
        ),
        "resolution": tpl["resolution"].format(
            retries=rng.choice([3, 5]),
            endpoint=rng.choice(_ENDPOINTS),
            new_seconds=rng.choice([60, 90, 120]),
            table=rng.choice(_TABLES),
            file=rng.choice(_FILES),
            line=rng.randint(10, 500),
        ),
        "context": tpl["context"].format(
            file=rng.choice(_FILES),
            line=rng.randint(10, 500),
        ),
        "approach": tpl["approach"],
        "tags": json.dumps([
            t.format(service_tag=_SERVICE_TAGS[svc_i]) for t in tpl["tags"]
        ]),
        "outcome": tpl["outcome"],
        "evidence": tpl["evidence"].format(endpoint=rng.choice(_ENDPOINTS)),
        "status": rng.choice(_STATUSES),
        "owner": f"dev{rng.randint(1, 5)}",
    }
    rendered["fingerprint"] = hashlib.md5(
        f"{rendered['error']}|{rendered['resolution']}".encode()
    ).hexdigest()
    return rendered


def generate_issues(n: int = 80) -> List[Dict]:
    """Genera n issues sintéticos (sin duplicados)."""
    seen_fps = set()
    issues = []
    for i in range(n * 3):  # sobregenerar para cubrir colisiones de fingerprint
        if len(issues) >= n:
            break
        tpl = _ISSUE_TEMPLATES[i % len(_ISSUE_TEMPLATES)]
        issue = _render_template(tpl, i)
        if issue["fingerprint"] not in seen_fps:
            seen_fps.add(issue["fingerprint"])
            issues.append(issue)
    return issues[:n]


def generate_near_duplicate_issues(base_issues: List[Dict], k: int = 10) -> List[Dict]:
    """
    Genera k near-duplicates de issues existentes.
    Cambia pocas palabras para que Jaccard similarity sea alta pero no 1.0.
    """
    rng = random.Random(99)
    near_dups = []
    for _ in range(k):
        original = rng.choice(base_issues)
        dup = original.copy()
        # Pequeña modificación al error (diferente fingerprint, pero similar)
        dup["error"] = original["error"].replace("refused", "rejected").replace("Timeout", "Slow response")
        dup["fingerprint"] = hashlib.md5(
            f"{dup['error']}|{dup['resolution']}".encode()
        ).hexdigest()
        dup["status"] = "verified"
        dup["owner"] = "dev_dup"
        near_dups.append(dup)
    return near_dups


def generate_exact_duplicate_issues(base_issues: List[Dict], k: int = 5) -> List[Dict]:
    """
    Genera k duplicados exactos (mismo fingerprint).
    Sirven para testear que el merge los detecta y los descarta.
    """
    rng = random.Random(77)
    return [rng.choice(base_issues).copy() for _ in range(k)]


# ============================================================
# Templates de documentación
# ============================================================

_DOC_CHUNKS = [
    # Constraints (genéricos de VELMA)
    {
        "doc_source": "project-rules.md",
        "chunk_title": "Constraint: Solo humano puede archivar",
        "chunk_body": "La operacion archived en issues_log solo la puede ejecutar un humano. El agente no debe marcar entradas como archivadas de forma autonoma. Siempre requerir confirmacion humana.",
        "chunk_type": "constraint",
        "verified": 1,
    },
    {
        "doc_source": "project-rules.md",
        "chunk_title": "Constraint: Evidencia obligatoria para success",
        "chunk_body": "Solo marcar outcome=success cuando hay evidencia verificable. NUNCA marcar success porque el codigo se ve correcto sin evidencia real como test output o build log.",
        "chunk_type": "constraint",
        "verified": 1,
    },
    {
        "doc_source": "project-rules.md",
        "chunk_title": "Constraint: No usar resultados con baja confianza",
        "chunk_body": "Si la similitud del resultado recuperado del knowledge base es menor a 0.75, el agente no lo usa como contexto. Debe razonar desde cero para evitar alucinaciones.",
        "chunk_type": "constraint",
        "verified": 1,
    },
    # Rules
    {
        "doc_source": "project-rules.md",
        "chunk_title": "Regla: Score de confianza minimo",
        "chunk_body": "El score minimo de confianza para usar un resultado del KB es 0.75. Por debajo de ese threshold, razonar desde cero. Documentar si se usa conocimiento con score bajo.",
        "chunk_type": "rule",
        "verified": 1,
    },
    {
        "doc_source": "project-rules.md",
        "chunk_title": "Regla: Citar fuente del knowledge base",
        "chunk_body": "Cada vez que el agente usa una entrada del knowledge base, debe indicar el ID y el score de similitud. Ejemplo: Basandome en el issue #42 (similitud: 0.89).",
        "chunk_type": "rule",
        "verified": 1,
    },
    {
        "doc_source": "project-rules.md",
        "chunk_title": "Regla: Buscar antes de razonar",
        "chunk_body": "Antes de intentar resolver un problema, buscar en el knowledge base si existe un issue similar ya resuelto. Esto evita repetir trabajo y reduce tokens consumidos.",
        "chunk_type": "rule",
        "verified": 1,
    },
    # Procedures
    {
        "doc_source": "CLAUDE.md",
        "chunk_title": "Procedimiento: Registrar issue en knowledge base",
        "chunk_body": "Al encontrar un error: 1. Buscar en issues_log antes de resolver. 2. Registrar cada intento fallido en attempts[]. 3. Solo marcar outcome=success con evidencia real. 4. Nunca marcar success sin evidencia.",
        "chunk_type": "procedure",
        "verified": 1,
    },
    {
        "doc_source": "CLAUDE.md",
        "chunk_title": "Procedimiento: Session summary al cerrar",
        "chunk_body": "Al cerrar la sesion, generar session_summary en reasoning_log. Esto NO es opcional. Incluir: task, approach, outcome, status=raw, owner=claude.",
        "chunk_type": "procedure",
        "verified": 1,
    },
    {
        "doc_source": "CLAUDE.md",
        "chunk_title": "Procedimiento: Verificar hash antes de leer archivo",
        "chunk_body": "Antes de leer un archivo, verificar su hash en files_index. Si el hash no cambio, usar el summary guardado. Esto evita re-leer archivos sin cambios y reduce tokens.",
        "chunk_type": "procedure",
        "verified": 1,
    },
    # Concepts
    {
        "doc_source": "CLAUDE.md",
        "chunk_title": "Concepto: Knowledge Base VELMA",
        "chunk_body": "VELMA es un sistema de memoria persistente para agentes de IA. Almacena issues resueltos, documentacion, constraints y razonamiento entre sesiones usando SQLite con FTS5 y embeddings.",
        "chunk_type": "concept",
        "verified": 1,
    },
    {
        "doc_source": "CLAUDE.md",
        "chunk_title": "Concepto: Ciclo de vida raw-verified-merged-archived",
        "chunk_body": "Las entradas en VELMA siguen el ciclo: raw (sin revisar), verified (aprobada por humano), merged (en shared), archived (obsoleta). Solo humanos archivan.",
        "chunk_type": "concept",
        "verified": 1,
    },
    # Examples
    {
        "doc_source": "CLAUDE.md",
        "chunk_title": "Ejemplo: Registrar issue resuelto",
        "chunk_body": "Ejemplo de registro correcto: INSERT INTO issues_log con outcome=success y evidence=test PASSED (3/3). La evidencia es obligatoria para marcar success.",
        "chunk_type": "example",
        "verified": 1,
    },
    {
        "doc_source": "CLAUDE.md",
        "chunk_title": "Ejemplo: Citar fuente del KB",
        "chunk_body": "Ejemplo de cita correcta: Basandome en el issue #15 (similitud: 0.87), el error de conexion se resuelve agregando retry con backoff exponencial.",
        "chunk_type": "example",
        "verified": 1,
    },
]


def generate_docs() -> List[Dict]:
    """Retorna la lista de chunks de documentación con order_in_doc asignado."""
    docs = []
    for i, chunk in enumerate(_DOC_CHUNKS):
        doc = chunk.copy()
        doc["order_in_doc"] = i
        doc["applies_to"] = json.dumps(["default"])
        doc["hash"] = hashlib.md5(
            f"{doc['chunk_title']}{doc['chunk_body']}".encode()
        ).hexdigest()
        docs.append(doc)
    return docs


# ============================================================
# Populador de DB
# ============================================================

def populate_db(conn: sqlite3.Connection, n_issues: int = 80) -> Dict:
    """
    Puebla la DB con datos sintéticos.
    Retorna estadísticas de lo insertado.
    """
    cursor = conn.cursor()
    stats = {"issues": 0, "docs": 0}

    # Insertar issues
    issues = generate_issues(n_issues)
    for issue in issues:
        try:
            cursor.execute("""
                INSERT INTO issues_log
                (error, resolution, context, approach, attempts, tags,
                 outcome, evidence, status, fingerprint, owner)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                issue["error"],
                issue["resolution"],
                issue["context"],
                issue["approach"],
                issue.get("attempts", "[]"),
                issue["tags"],
                issue["outcome"],
                issue["evidence"],
                issue["status"],
                issue["fingerprint"],
                issue["owner"],
            ))
            stats["issues"] += 1
        except sqlite3.IntegrityError:
            pass  # fingerprint duplicado → skip

    # Insertar docs
    docs = generate_docs()
    for doc in docs:
        try:
            cursor.execute("""
                INSERT INTO docs_index
                (doc_source, chunk_title, chunk_body, chunk_type,
                 order_in_doc, hash, verified, applies_to)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                doc["doc_source"],
                doc["chunk_title"],
                doc["chunk_body"],
                doc["chunk_type"],
                doc["order_in_doc"],
                doc["hash"],
                doc["verified"],
                doc["applies_to"],
            ))
            stats["docs"] += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    return stats


# ============================================================
# CLI rápido para inspección manual
# ============================================================

if __name__ == "__main__":
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else "test_data.db"

    # Crear schema mínimo
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Importar setup
    root = str(__file__.replace("tests/fixtures/generate_test_data.py", ""))
    sys.path.insert(0, root)
    from setup_kb import create_database as _create_db_file

    import os
    if os.path.exists(db_path):
        os.remove(db_path)
    _create_db_file.__globals__["DB_NAME"] = db_path
    _create_db_file()

    conn = sqlite3.connect(db_path)
    stats = populate_db(conn, n_issues=80)
    conn.close()

    print(f"DB creada: {db_path}")
    print(f"  Issues: {stats['issues']}")
    print(f"  Docs:   {stats['docs']}")
