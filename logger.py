#!/usr/bin/env python3
"""
VELMA - Knowledge Logger
Permite a los agentes registrar issues y razonamientos de forma estandarizada.
"""

import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime
from pathlib import Path

# Agregar carpeta actual al path para importar kb_utils
sys.path.insert(0, str(Path(__file__).parent))
from kb_utils import encode_text, compute_hash, format_json_field

DB_NAME = os.getenv("DB_PATH", "knowledge.db")

def log_issue(error, resolution, context, approach, attempts, tags, evidence, owner):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Generar fingerprint único
    fp = compute_hash(f"{error}|{resolution}")
    
    # Generar embedding del error + approach para búsqueda semántica
    embedding = encode_text(f"{error} {approach}")
    
    try:
        c.execute("""
            INSERT INTO issues_log 
            (error, resolution, context, approach, attempts, tags, outcome, evidence, status, fingerprint, embedding, owner)
            VALUES (?, ?, ?, ?, ?, ?, 'success', ?, 'raw', ?, ?, ?)
        """, (
            error, resolution, context, approach, 
            format_json_field(attempts), 
            format_json_field(tags),
            evidence, fp, embedding, owner
        ))
        conn.commit()
        print(f"[OK] Issue registrado como 'raw'. ID: {c.lastrowid}")
        return True
    except sqlite3.IntegrityError:
        print("[!] Error: Este issue ya existe en la base de datos (fingerprint duplicado).")
        return False
    finally:
        conn.close()

def log_reasoning(task, approach, outcome, owner):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO reasoning_log (task, approach, outcome, status, owner)
            VALUES (?, ?, ?, 'raw', ?)
        """, (task, approach, outcome, owner))
        conn.commit()
        print(f"[OK] Razonamiento registrado como 'raw'. ID: {c.lastrowid}")
        return True
    except Exception as e:
        print(f"[ERR] No se pudo registrar razonamiento: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VELMA Logger - Registra conocimiento")
    subparsers = parser.add_subparsers(dest="command")

    # Comando para Issues
    p_issue = subparsers.add_parser("issue")
    p_issue.add_argument("--error", required=True)
    p_issue.add_argument("--resolution", required=True)
    p_issue.add_argument("--context", default="N/A")
    p_issue.add_argument("--approach", default="")
    p_issue.add_argument("--attempts", default="[]")
    p_issue.add_argument("--tags", default="[]")
    p_issue.add_argument("--evidence", default="")
    p_issue.add_argument("--owner", default="agent")

    # Comando para Razonamientos
    p_reason = subparsers.add_parser("reason")
    p_reason.add_argument("--task", required=True)
    p_reason.add_argument("--approach", required=True)
    p_reason.add_argument("--outcome", default="")
    p_reason.add_argument("--owner", default="agent")

    args = parser.parse_args()

    if args.command == "issue":
        log_issue(args.error, args.resolution, args.context, args.approach, 
                  json.loads(args.attempts), json.loads(args.tags), 
                  args.evidence, args.owner)
    elif args.command == "reason":
        log_reasoning(args.task, args.approach, args.outcome, args.owner)
