#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import atexit
import signal
from mcp.server.fastmcp import FastMCP
from search import search_knowledge
from logger import log_issue, log_reasoning, log_discovery

# Ollama environment variables
OLLAMA_EMBED_MODEL = os.getenv('OLLAMA_EMBED_MODEL', 'nomic-embed-text')
OLLAMA_STARTUP_TIMEOUT = int(os.getenv('OLLAMA_STARTUP_TIMEOUT', '15'))

_ollama_process = None

def _ollama_is_running() -> bool:
    try:
        import ollama
        ollama.list()
        return True
    except:
        return False

def _start_ollama():
    global _ollama_process
    print("[VELMA] Ollama no esta corriendo. Iniciando...", file=sys.stderr)
    _ollama_process = subprocess.Popen(
        ["ollama", "serve"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    for _ in range(OLLAMA_STARTUP_TIMEOUT):
        time.sleep(1)
        if _ollama_is_running():
            print("[VELMA] Ollama iniciado.", file=sys.stderr)
            return
    raise RuntimeError(
        f"Ollama no respondio en {OLLAMA_STARTUP_TIMEOUT}s. "
        "Verifica que este instalado: https://ollama.com"
    )

def _ensure_model():
    import ollama
    models = ollama.list()
    names = [m.get('model', m.get('name', '')) for m in models.get('models', [])]
    if not any(OLLAMA_EMBED_MODEL in n for n in names):
        print(f"[VELMA] Descargando {OLLAMA_EMBED_MODEL}...", file=sys.stderr)
        ollama.pull(OLLAMA_EMBED_MODEL)
        print(f"[VELMA] Modelo listo.", file=sys.stderr)

def ensure_ollama_ready():
    if not _ollama_is_running():
        _start_ollama()
    _ensure_model()

def shutdown_ollama():
    global _ollama_process
    if _ollama_process is not None:
        print("[VELMA] Cerrando Ollama...", file=sys.stderr)
        _ollama_process.terminate()
        _ollama_process = None

atexit.register(shutdown_ollama)
signal.signal(signal.SIGTERM, lambda *_: shutdown_ollama())
signal.signal(signal.SIGINT, lambda *_: shutdown_ollama())

# MCP Server
mcp = FastMCP("velma")

@mcp.tool()
def velma_search(query: str, table: str = "all") -> list[dict]:
    """Busca en la knowledge base de VELMA."""
    return search_knowledge(query, table)

@mcp.tool()
def velma_log_issue(error: str, resolution: str, approach: str, evidence: str, context: str = "N/A") -> str:
    """Registra un issue resuelto. Llamar SIEMPRE al terminar una tarea exitosa."""
    success = log_issue(error, resolution, context, approach, [], [], evidence, owner="mcp-agent")
    if success:
        return "Issue registrado exitosamente."
    return "Error: Issue duplicado o fallo en el registro."

@mcp.tool()
def velma_log_reason(task: str, approach: str, outcome: str) -> str:
    """Registra el razonamiento. Llamar SIEMPRE junto a velma_log_issue."""
    success = log_reasoning(task, approach, outcome, owner="mcp-agent")
    if success:
        return "Razonamiento registrado exitosamente."
    return "Error al registrar razonamiento."

@mcp.tool()
def velma_log_discovery(title: str, content: str, source: str = "manual") -> str:
    """Registra un descubrimiento tecnico."""
    success = log_discovery(title, content, source, owner="mcp-agent")
    if success:
        return "Descubrimiento registrado exitosamente."
    return "Error al registrar descubrimiento."

@mcp.tool()
def velma_context(limit: int = 10) -> list[dict]:
    """Retorna las ultimas N entradas de reasoning_log para obtener contexto."""
    return search_knowledge("", "reasoning", limit=limit)

if __name__ == "__main__":
    ensure_ollama_ready()
    mcp.run()
