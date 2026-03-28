"""
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
    """Calcula fecha de expiración"""
    expiry = datetime.now() + timedelta(days=days)
    return expiry.isoformat()

def detect_chunk_type(title: str, body: str) -> str:
    """Detecta automáticamente el tipo de chunk basado en contenido"""
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
# Embedding Model (Ollama Only)
# ============================================================

import os
OLLAMA_EMBED_MODEL = os.getenv('OLLAMA_EMBED_MODEL', 'nomic-embed-text')

def encode_text(text: str) -> bytes:
    """Genera embedding BLOB para un texto usando Ollama"""
    if not text:
        return None
    
    import ollama
    resp = ollama.embeddings(model=OLLAMA_EMBED_MODEL, prompt=text)
    vec = np.array(resp['embedding'], dtype=np.float32)
    return vec.tobytes()

def encode_texts(texts: list) -> list:
    """Genera embeddings en batch usando Ollama"""
    if not texts:
        return []
    
    import ollama
    results = []
    for text in texts:
        resp = ollama.embeddings(model=OLLAMA_EMBED_MODEL, prompt=text)
        vec = np.array(resp['embedding'], dtype=np.float32)
        results.append(vec.tobytes())
    return results

# ============================================================
# Ollama Enricher (Traducción y Enriquecimiento Opcional)
# ============================================================

class OllamaEnricher:
    """Usa Ollama local para traducir y enriquecer textos técnicos."""
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
        """Genera versión bilingüe del texto si Ollama está disponible."""
        if not self.available or not text:
            return text
        import ollama
        prompt = f"Translate and enrich this technical text between Spanish and English. Output only the consolidated bilingual result:\n{text}"
        try:
            response = ollama.generate(model=self.model, prompt=prompt)
            return f"{text}\n\n{response['response'].strip()}"
        except:
            return text
