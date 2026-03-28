"""
VELMA - Knowledge Base Utilities
Funciones auxiliares para el sistema de knowledge base
"""

import hashlib
import json
from datetime import datetime, timedelta

def compute_hash(text: str) -> str:
    """Calcula hash MD5 de un texto"""
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def compute_file_hash(content: bytes) -> str:
    """Calcula hash MD5 del contenido de un archivo"""
    return hashlib.md5(content).hexdigest()

def parse_json_field(field: str) -> list:
    """Parsea un campo JSON de la base de datos"""
    if field is None:
        return []
    try:
        return json.loads(field)
    except:
        return []

def format_json_field(data: list or dict) -> str:
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
    
    # Palabras clave para constraints
    constraint_keywords = ['nunca', 'siempre', 'obligatorio', 'prohibido', 'exactamente', 'solo', 'único']
    if any(kw in title_lower or kw in body_lower for kw in constraint_keywords):
        return 'constraint'
    
    # Palabras clave para rules
    rule_keywords = ['regla', 'política', 'debe', 'requiere', 'acumula', 'canjea']
    if any(kw in title_lower or kw in body_lower for kw in rule_keywords):
        return 'rule'
    
    # Palabras clave para procedures
    procedure_keywords = ['paso', 'cómo', 'para', 'seguir', 'proceso', 'registrar']
    if any(kw in title_lower or kw in body_lower for kw in procedure_keywords):
        return 'procedure'
    
    # Palabras clave para examples
    example_keywords = ['ejemplo', 'ilustración', 'caso', 'muestra']
    if any(kw in title_lower or kw in body_lower for kw in example_keywords):
        return 'example'
    
    return 'concept'

def get_chunk_weight(chunk_type: str) -> int:
    """Retorna el peso de un tipo de chunk para ranking"""
    weights = {
        'constraint': 10,
        'rule': 8,
        'procedure': 7,
        'concept': 5,
        'example': 3
    }
    return weights.get(chunk_type, 5)

def cosine_similarity(vec1, vec2):
    """Calcula similitud coseno entre dos vectores"""
    import numpy as np
    
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
# Embedding Model (singleton — carga el modelo una sola vez)
# ============================================================

_embedding_model = None

def get_embedding_model():
    """
    Retorna el modelo all-MiniLM-L6-v2 como singleton.
    La primera llamada descarga/carga el modelo (~22MB).
    Las llamadas siguientes reutilizan la instancia en memoria.
    """
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model


def encode_text(text: str) -> bytes:
    """
    Genera el embedding de un texto y lo retorna como BLOB (bytes float32).
    Listo para INSERT directo en SQLite.
    """
    import numpy as np
    model = get_embedding_model()
    vec = model.encode(text, convert_to_numpy=True)
    return vec.astype(np.float32).tobytes()


def encode_texts(texts: list) -> list:
    """
    Genera embeddings en batch. Más eficiente que llamar encode_text N veces.
    Retorna lista de bytes, uno por texto.
    """
    import numpy as np
    if not texts:
        return []
    model = get_embedding_model()
    vecs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    return [v.astype(np.float32).tobytes() for v in vecs]
