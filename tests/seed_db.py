#!/usr/bin/env python3
"""
VELMA - Seed script
Lee los datos generados por Gemini (seed_data.json) e inserta en knowledge.db
con embeddings reales usando all-MiniLM-L6-v2.

Uso:
    python tests/seed_db.py seed_data.json
    python tests/seed_db.py seed_data.json --db knowledge.db
"""

import sys
import json
import hashlib
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from kb_utils import encode_text, encode_texts


def make_fingerprint(error: str, resolution: str = "") -> str:
    return hashlib.md5(f"{error}|{resolution}".encode()).hexdigest()


def insert_issues(conn: sqlite3.Connection, issues: list, verbose: bool = True) -> int:
    """Inserta issues con embeddings. Retorna cantidad insertada."""
    c = conn.cursor()
    inserted = 0
    skipped = 0

    print(f"  Generando embeddings para {len(issues)} issues...")
    # Texto para embedding: error + approach (lo más rico semánticamente)
    texts = [f"{i['error']} {i.get('approach', '')}" for i in issues]
    embeddings = encode_texts(texts)

    for issue, emb in zip(issues, embeddings):
        fp = make_fingerprint(issue["error"], issue.get("resolution", ""))
        try:
            c.execute("""
                INSERT INTO issues_log
                (error, resolution, context, approach, attempts, tags,
                 outcome, evidence, status, fingerprint, embedding, owner,
                 created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        datetime('now'), datetime('now', '+90 days'))
            """, (
                issue["error"],
                issue.get("resolution", ""),
                issue.get("context", ""),
                issue.get("approach", ""),
                json.dumps(issue.get("attempts", []), ensure_ascii=False),
                json.dumps(issue.get("tags", []), ensure_ascii=False),
                issue.get("outcome", "success"),
                issue.get("evidence", ""),
                issue.get("status", "verified"),
                fp,
                emb,
                issue.get("owner", "gemini"),
            ))
            inserted += 1
            if verbose:
                print(f"    [+] {issue['error'][:70]}")
        except sqlite3.IntegrityError:
            skipped += 1
            if verbose:
                print(f"    [skip] duplicado: {issue['error'][:60]}")

    conn.commit()
    print(f"  Issues: {inserted} insertados, {skipped} duplicados omitidos")
    return inserted


def insert_docs(conn: sqlite3.Connection, docs: list, verbose: bool = True) -> int:
    """Inserta chunks de docs con embeddings. Retorna cantidad insertada."""
    c = conn.cursor()
    inserted = 0
    skipped = 0

    print(f"  Generando embeddings para {len(docs)} chunks...")
    texts = [f"{d['chunk_title']} {d['chunk_body']}" for d in docs]
    embeddings = encode_texts(texts)

    for i, (doc, emb) in enumerate(zip(docs, embeddings)):
        chunk_hash = hashlib.md5(
            f"{doc['chunk_title']}{doc['chunk_body']}".encode()
        ).hexdigest()

        # Verificar si ya existe por hash
        existing = c.execute(
            "SELECT id FROM docs_index WHERE hash = ?", (chunk_hash,)
        ).fetchone()
        if existing:
            skipped += 1
            if verbose:
                print(f"    [skip] ya existe: {doc['chunk_title'][:55]}")
            continue

        c.execute("""
            INSERT INTO docs_index
            (doc_source, chunk_title, chunk_body, chunk_type, order_in_doc,
             hash, verified, applies_to, updated_at, embedding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
        """, (
            doc.get("doc_source", "chakana-reglas.md"),
            doc["chunk_title"],
            doc["chunk_body"],
            doc.get("chunk_type", "concept"),
            doc.get("order_in_doc", 100 + i),
            chunk_hash,
            doc.get("verified", 1),
            json.dumps(doc.get("applies_to", ["chakana", "repovg"]), ensure_ascii=False),
            emb,
        ))
        inserted += 1
        if verbose:
            print(f"    [+] [{doc.get('chunk_type', '?'):12}] {doc['chunk_title'][:55]}")

    conn.commit()
    print(f"  Docs: {inserted} insertados, {skipped} duplicados omitidos")
    return inserted


def main():
    parser = argparse.ArgumentParser(description="VELMA - Seed DB desde JSON de Gemini")
    parser.add_argument("json_file", help="Archivo JSON con {issues: [...], docs: [...]}")
    parser.add_argument("--db", default="knowledge.db", help="Path a la DB (default: knowledge.db)")
    parser.add_argument("--quiet", "-q", action="store_true", help="Menos output")
    args = parser.parse_args()

    json_path = Path(args.json_file)
    if not json_path.exists():
        print(f"[ERROR] No se encontró el archivo: {json_path}")
        return 1

    print(f"\n{'='*60}")
    print("  VELMA - Seed DB con datos de Gemini")
    print(f"  DB:   {args.db}")
    print(f"  JSON: {json_path}")
    print(f"{'='*60}\n")

    # Leer JSON
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON inválido: {e}")
        return 1

    issues = data.get("issues", [])
    docs = data.get("docs", [])
    print(f"  Datos a insertar: {len(issues)} issues, {len(docs)} docs")

    # Conectar a DB
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    verbose = not args.quiet

    print(f"\n[1/2] Insertando issues...")
    n_issues = insert_issues(conn, issues, verbose)

    print(f"\n[2/2] Insertando docs...")
    n_docs = insert_docs(conn, docs, verbose)

    # Stats finales
    c = conn.cursor()
    total_issues = c.execute("SELECT COUNT(*) FROM issues_log").fetchone()[0]
    total_docs = c.execute("SELECT COUNT(*) FROM docs_index").fetchone()[0]
    issues_with_emb = c.execute("SELECT COUNT(*) FROM issues_log WHERE embedding IS NOT NULL").fetchone()[0]
    docs_with_emb = c.execute("SELECT COUNT(*) FROM docs_index WHERE embedding IS NOT NULL").fetchone()[0]

    conn.close()

    print(f"\n{'='*60}")
    print("  RESULTADO FINAL")
    print(f"{'='*60}")
    print(f"  issues_log:  {total_issues} total  ({issues_with_emb} con embedding)")
    print(f"  docs_index:  {total_docs} total  ({docs_with_emb} con embedding)")
    print(f"  Insertados:  {n_issues} issues + {n_docs} docs nuevos")
    print(f"{'='*60}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
