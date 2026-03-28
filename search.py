#!/usr/bin/env python3
"""
VELMA - Knowledge Base Search (Fase 3)
Búsqueda híbrida FTS5+vector con RRF
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

from kb_utils import cosine_similarity, encode_text, OllamaEnricher, get_db_path

DB_NAME = get_db_path()
DEFAULT_K = 60
MIN_CONFIDENCE_SCORE = 0.50
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.2:1b')

@dataclass
class SearchResult:
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
    def __init__(self, db_path: str = DB_NAME, use_ollama: bool = True):
        self.db_path = db_path
        self.use_ollama = use_ollama
        self.enricher = OllamaEnricher(model=OLLAMA_MODEL) if use_ollama else None
        self.conn = None
        self.cursor = None
    
    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        return self
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
            self.cursor = None
    
    def __enter__(self):
        return self.connect()
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def _sanitize_fts_query(self, query: str) -> str:
        if not query:
            return '""'
        terms = query.strip().split()
        return " ".join(f'"{term}"' for term in terms) if terms else '""'

    def search_fts_issues(self, query: str, limit: int = 20) -> List[Tuple[int, float]]:
        safe_query = self._sanitize_fts_query(query)
        try:
            self.cursor.execute("""
                SELECT rowid, rank
                FROM issues_log_fts
                WHERE issues_log_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (safe_query, limit))
            
            results = []
            for row in self.cursor.fetchall():
                rank = row['rank'] if row['rank'] else -1000
                score = 1.0 / (1.0 + abs(rank))
                results.append((row['rowid'], score))
            return results
        except Exception as e:
            return []
    
    def search_fts_docs(self, query: str, limit: int = 20) -> List[Tuple[int, float]]:
        safe_query = self._sanitize_fts_query(query)
        try:
            self.cursor.execute("""
                SELECT rowid, rank
                FROM docs_index_fts
                WHERE docs_index_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (safe_query, limit))
            
            results = []
            for row in self.cursor.fetchall():
                rank = row['rank'] if row['rank'] else -1000
                score = 1.0 / (1.0 + abs(rank))
                results.append((row['rowid'], score))
            return results
        except Exception as e:
            return []
    
    def search_fts_files(self, query: str, limit: int = 20) -> List[Tuple[int, float]]:
        safe_query = self._sanitize_fts_query(query)
        try:
            self.cursor.execute("""
                SELECT rowid, rank
                FROM files_index_fts
                WHERE files_index_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (safe_query, limit))
            
            results = []
            for row in self.cursor.fetchall():
                rank = row['rank'] if row['rank'] else -1000
                score = 1.0 / (1.0 + abs(rank))
                results.append((row['rowid'], score))
            return results
        except Exception as e:
            return []
    
    def search_fts_reasoning(self, query: str, limit: int = 20) -> List[Tuple[int, float]]:
        safe_query = self._sanitize_fts_query(query)
        try:
            self.cursor.execute("""
                SELECT rowid, rank
                FROM reasoning_log_fts
                WHERE reasoning_log_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (safe_query, limit))
            
            results = []
            for row in self.cursor.fetchall():
                rank = row['rank'] if row['rank'] else -1000
                score = 1.0 / (1.0 + abs(rank))
                results.append((row['rowid'], score))
            return results
        except Exception as e:
            return []
    
    def reciprocal_rank_fusion(self, rankings: List[List[Tuple[int, float]]], k: int = DEFAULT_K) -> Dict[int, float]:
        scores = {}
        for ranking in rankings:
            for rank, (doc_id, _) in enumerate(ranking):
                if doc_id not in scores:
                    scores[doc_id] = 0
                scores[doc_id] += 1.0 / (k + rank + 1)
        return scores

    def search_vector_issues(self, query_embedding: bytes, limit: int = 20) -> List[Tuple[int, float]]:
        if query_embedding is None:
            return []
        try:
            self.cursor.execute("SELECT id, embedding FROM issues_log WHERE embedding IS NOT NULL")
            results = []
            for row in self.cursor.fetchall():
                sim = cosine_similarity(query_embedding, row['embedding'])
                if sim >= MIN_CONFIDENCE_SCORE:
                    results.append((row['id'], sim))
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
        except Exception as e:
            return []

    def search_vector_docs(self, query_embedding: bytes, limit: int = 20) -> List[Tuple[int, float]]:
        if query_embedding is None:
            return []
        try:
            self.cursor.execute("SELECT id, embedding FROM docs_index WHERE embedding IS NOT NULL")
            results = []
            for row in self.cursor.fetchall():
                sim = cosine_similarity(query_embedding, row['embedding'])
                if sim >= MIN_CONFIDENCE_SCORE:
                    results.append((row['id'], sim))
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:limit]
        except Exception as e:
            return []

    def search_issues(self, query: str, limit: int = 10) -> List[SearchResult]:
        fts_results = self.search_fts_issues(query, limit * 2)
        try:
            query_emb = encode_text(query)
            vector_results = self.search_vector_issues(query_emb, limit * 2)
        except Exception:
            vector_results = []

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
                    content=f"Error: {row['error']}\\n\\nResolucion: {row['resolution'] or 'N/A'}",
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
        fts_results = self.search_fts_docs(query, limit * 2)
        try:
            query_emb = encode_text(query)
            vector_results = self.search_vector_docs(query_emb, limit * 2)
        except Exception:
            vector_results = []

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
                    metadata={'language': row['language'], 'computed_at': row['computed_at']}
                ))
        return results
    
    def search_reasoning(self, query: str, limit: int = 10) -> List[SearchResult]:
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
                    content=f"Enfoque: {row['approach']}\\n\\nResultado: {row['outcome'] or 'N/A'}",
                    score=fts_score,
                    metadata={'status': row['status'], 'owner': row['owner'], 'created_at': row['created_at']}
                ))
        return results
    
    def search_all(self, query: str, limit: int = 10) -> Dict[str, List[SearchResult]]:
        return {
            'issues': self.search_issues(query, limit),
            'docs': self.search_docs(query, limit),
            'files': self.search_files(query, limit),
            'reasoning': self.search_reasoning(query, limit)
        }
    
    def _get_chunk_weight(self, chunk_type: str) -> int:
        weights = {'constraint': 10, 'rule': 8, 'procedure': 7, 'concept': 5, 'example': 3}
        return weights.get(chunk_type, 5)


def search_knowledge(query: str, table: str = "all", limit: int = 10) -> list[dict]:
    """Función pura importable para buscar en el KB."""
    with KnowledgeSearch() as search:
        if table == 'all':
            results = search.search_all(query, limit)
            all_res = []
            for k, v in results.items():
                all_res.extend([item.to_dict() for item in v])
            return all_res
        elif table == 'issues':
            return [item.to_dict() for item in search.search_issues(query, limit)]
        elif table == 'docs':
            return [item.to_dict() for item in search.search_docs(query, limit)]
        elif table == 'files':
            return [item.to_dict() for item in search.search_files(query, limit)]
        elif table == 'reasoning':
            return [item.to_dict() for item in search.search_reasoning(query, limit)]
    return []

def cli_search():
    parser = argparse.ArgumentParser(description='VELMA Knowledge Base Search')
    parser.add_argument('query', help='Término de búsqueda')
    parser.add_argument('--table', '-t', choices=['issues', 'docs', 'files', 'reasoning', 'all'],
                        default='all', help='Tabla a buscar')
    parser.add_argument('--limit', '-l', type=int, default=10, help='Límite de resultados')
    parser.add_argument('--json', '-j', action='store_true', help='Output en JSON')
    
    args = parser.parse_args()
    results = search_knowledge(args.query, args.table, args.limit)
    
    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print("="*60)
        print(f"  Resultados para: '{args.query}'")
        print("="*60)
        
        for item in results:
            print(f"\n  [{item['score']:.3f}] [{item['table'].upper()}] {item['title']}")
            print(f"      {item['content'][:200].replace(chr(10), ' ')}...")

if __name__ == "__main__":
    cli_search()
