"""
VELMA - Knowledge Base Utilities
Funciones auxiliares para el sistema de knowledge base
"""

import os
import hashlib
import json
import sqlite3
import urllib.request
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict

def get_db_path():
    """Retorna la ruta absoluta a la base de datos knowledge.db"""
    return str(Path(__file__).parent / "knowledge.db")

def get_metadata(key: str, default: any = None) -> any:
    """Obtiene un valor de la tabla metadata"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM metadata WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else default
    except:
        return default

def set_metadata(key: str, value: any):
    """Guarda un valor en la tabla metadata"""
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO metadata (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key, str(value)))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def check_for_updates() -> Optional[Dict]:
    """
    Comprueba si hay actualizaciones del tool o del KB.
    Frecuencia: una vez cada 24h.
    Retorna datos de la actualizacion si hay una disponible, o None.
    """
    last_check = get_metadata('last_update_check')
    
    # Si ya se comprobo hace menos de 24h, omitir
    if last_check:
        try:
            last_date = datetime.fromisoformat(last_check)
            if datetime.now() < last_date + timedelta(hours=24):
                return None
        except:
            pass
            
    # Marcar comprobacion ahora (para evitar reintento inmediato si falla red)
    set_metadata('last_update_check', datetime.now().isoformat())
    
    # URL de manifiesto (Placeholder, configurable via .env)
    update_url = os.getenv('VELMA_UPDATE_URL')
    if not update_url:
        return None
        
    try:
        # Peticion no bloqueante (con timeout corto)
        with urllib.request.urlopen(update_url, timeout=2) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                
                # Leer version local
                version_path = Path(__file__).parent / "version.txt"
                local_version = version_path.read_text().strip() if version_path.exists() else "0.0.0"
                
                remote_version = data.get('tool_version', local_version)
                
                # Comparar versiones
                if remote_version > local_version:
                    update_info = {
                        'current': local_version,
                        'latest': remote_version,
                        'message': data.get('message', 'Nueva version disponible'),
                        'url': data.get('url', 'https://github.com/Gavanti/VELMA')
                    }
                    return update_info
    except:
        # Fallo de red silencioso
        pass
        
    return None

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
# Embedding Model (Ollama + fallback a SentenceTransformers)
# ============================================================

_embedding_model = None
_use_ollama_embeddings = None

def check_ollama_embeddings():
    """Verifica si Ollama esta disponible y tiene el modelo nomic-embed-text"""
    global _use_ollama_embeddings
    if _use_ollama_embeddings is not None:
        return _use_ollama_embeddings
    try:
        import ollama
        models = ollama.list()
        has_nomic = any('nomic-embed-text' in m.get('name', '') or 'nomic-embed-text' in m.get('model', '') for m in models.get('models', []))
        _use_ollama_embeddings = has_nomic
        return has_nomic
    except:
        _use_ollama_embeddings = False
        return False

def get_embedding_model():
    """Retorna el modelo fallback como singleton si Ollama no esta disponible."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
    return _embedding_model

def encode_text(text: str) -> bytes:
    """Genera embedding BLOB para un texto"""
    if not text: return None
    
    if check_ollama_embeddings():
        import ollama
        resp = ollama.embeddings(model='nomic-embed-text', prompt=text)
        vec = np.array(resp['embedding'], dtype=np.float32)
        return vec.tobytes()
    else:
        model = get_embedding_model()
        vec = model.encode(text, convert_to_numpy=True)
        return vec.astype(np.float32).tobytes()

def encode_texts(texts: list) -> list:
    """Genera embeddings en batch"""
    if not texts: return []
    
    if check_ollama_embeddings():
        import ollama
        results = []
        for text in texts:
            resp = ollama.embeddings(model='nomic-embed-text', prompt=text)
            vec = np.array(resp['embedding'], dtype=np.float32)
            results.append(vec.tobytes())
        return results
    else:
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
        prompt = f"Translate and enrich this technical text between Spanish and English. Output only the consolidated bilingual result:\n{text}"
        try:
            response = ollama.generate(model=self.model, prompt=prompt)
            return f"{text}\n\n{response['response'].strip()}"
        except:
            return text
