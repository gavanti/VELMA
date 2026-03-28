"""
Tests de integración: Multilingual & Ollama
Valida que la búsqueda híbrida ahora soporte queries en inglés contra datos en español.
"""

import pytest
import sqlite3
from search import KnowledgeSearch
from kb_utils import OllamaEnricher, encode_text, cosine_similarity

def test_multilingual_model_loading():
    """Verifica que el nuevo modelo multilingüe carga y genera dimensiones correctas."""
    text = "Hola mundo"
    emb = encode_text(text)
    # paraphrase-multilingual-MiniLM-L12-v2 tiene 384 dimensiones
    # Cada float32 son 4 bytes -> 384 * 4 = 1536 bytes
    assert len(emb) == 1536

def test_cosine_similarity_cross_language():
    """Test conceptual: similitud entre frases equivalentes en distintos idiomas."""
    # Nota: Este test depende de la calidad del modelo de embeddings
    es_emb = encode_text("error de conexión a la base de datos")
    en_emb = encode_text("database connection error")
    
    sim = cosine_similarity(es_emb, en_emb)
    print(f"Similitud cross-language (ES-EN): {sim:.4f}")
    # Un modelo multilingüe debería dar > 0.6 para estas frases
    assert sim > 0.6

def test_search_engine_multilingual_query(tmp_path):
    """Verifica que el motor de búsqueda encuentre docs en español usando queries en inglés."""
    from tests.conftest import _apply_schema
    db_file = tmp_path / "multi.db"
    conn = sqlite3.connect(str(db_file))
    _apply_schema(conn)
    
    # Insertar un doc solo en español con embedding multilingüe
    content = "El Aurio vale exactamente 0.01 dolares."
    emb = encode_text(content)
    conn.execute("""
        INSERT INTO docs_index (doc_source, chunk_title, chunk_body, chunk_type, embedding, hash)
        VALUES ('test.md', 'Valor Aurio', ?, 'constraint', ?, 'h1')
    """, (content, emb))
    conn.commit()
    conn.close()
    
    search = KnowledgeSearch(str(db_file), use_ollama=False) # Solo multilingüe puro primero
    search.connect()
    
    # Query en inglés
    results = search.search_docs("Aurio value in dollars", limit=5)
    
    assert len(results) > 0
    assert "Aurio" in results[0].content
    search.close()

def test_ollama_enricher_availability():
    """Verifica si Ollama está disponible en el entorno."""
    enricher = OllamaEnricher(model="llama3.2:1b")
    if enricher.available:
        text = "error de conexión"
        enriched = enricher.translate_and_enrich(text)
        assert len(enriched) > len(text)
        assert "connection" in enriched.lower()
    else:
        pytest.skip("Ollama no está corriendo en este entorno")
