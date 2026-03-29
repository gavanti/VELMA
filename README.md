<div align="center">

```text
       ##########################################################              ##########################################################       
    ##############################################################            ##############################################################    
    ##                                                          ##            ##                                                          ##    
    ##   ####################################################   ##            ##   ####################################################   ##    
    ##   ####################################################   ##            ##   ####################################################   ##    
    ##   ####################################################   ##            ##   ####################################################   ##    
    ##   ####################################################   ##   ######   ##   ####################################################   ##    
    ##   ####################################################   ########  ######   ####################################################   ##    
    ##   ####################################################   ######      ####   ####################################################   ##    
    ##   ####################################################   ##            ##   ####################################################   ##    
    ##   ####################################################   ##            ##   ####################################################   ##    
    ##   ####################################################   ##            ##   ####################################################   ##    
    ##   ####################################################   ##            ##   ####################################################   ##    
    ##                                                          ##            ##                                                          ##    
    ##############################################################            ##############################################################    
       ##########################################################              ##########################################################  
```

# VELMA - Knowledge Base Persistente para Agentes de IA

Sistema de memoria persistente para agentes de IA. Convierte el razonamiento en recuperación, eliminando la repetición de errores y anclando al agente en las reglas de negocio reales de tu proyecto.

> **Principio clave**: *Pensar es caro. Recordar es barato.*

</div>

---

## ⚡ Instalación Rápida (Un solo Enter)

Si estás en Windows (PowerShell), simplemente navega a tu proyecto y ejecuta el instalador mágico:

```powershell
irm https://raw.githubusercontent.com/gavanti/VELMA/main/install.ps1 | iex
```

El instalador:
1. Autodetecta el nombre de tu proyecto.
2. Descarga VELMA en una carpeta encapsulada (`./VELMA/`).
3. Instala [Ollama](https://ollama.com/) de forma silenciosa (si no lo tienes) y descarga los modelos ligeros necesarios.
4. Registra automáticamente la habilidad (Skill) para **Claude Code** y **OpenCode**.
5. Inicializa la base de datos y los protocolos de agente.

---

## 🧠 El Nuevo Modus Operandi (v1.0.0+)

VELMA ha evolucionado a una arquitectura nativa, limpia y ultra-rápida.

### 1. Servidor MCP (Model Context Protocol)
VELMA ya no depende únicamente de la terminal. Al iniciar Claude Code o OpenCode, VELMA arranca como un **Servidor MCP**.
Esto significa que el agente tiene herramientas nativas en su cerebro:
- `velma_search`: Para buscar reglas y soluciones pasadas.
- `velma_log_issue`: Para registrar bugs solucionados.
- `velma_log_reason`: Para guardar la lógica de un ticket.
- `velma_log_discovery`: Para extraer conceptos de la documentación.

### 2. Ollama Nativo (Cero límites)
Hemos eliminado las dependencias pesadas de HuggingFace. Todo el procesamiento semántico (embeddings) y bilingüe (español/inglés) ocurre 100% en tu máquina usando **Ollama** con el modelo `nomic-embed-text`. 
- **Privacidad total**: Tu código nunca sale de tu PC.
- **Sin límites**: No hay rate limits de APIs externas.

### 3. El Protocolo "HARD STOP"
VELMA impone una regla estricta a los agentes: **No pueden cerrar una tarea sin actualizar la memoria.**
Antes de decir "listo", el agente está forzado a registrar el error que arregló (`velma_log_issue`) y la estrategia que usó (`velma_log_reason`). Si no lo hace, el sistema se lo recordará.

---

## 🏗 Arquitectura y Stack Tecnológico

| Componente | Tecnología | Propósito |
|------------|------------|-----------|
| **Base de datos** | SQLite local | Base personal del repositorio, rápida y sin servidores. |
| **Búsqueda exacta** | FTS5 | Encuentra palabras clave y paths de archivos exactos. |
| **Búsqueda semántica** | Ollama (`nomic-embed-text`) | Entiende contexto y similitud de conceptos (ES/EN). |
| **Integración IA** | MCP Server (`FastMCP`) | Expone las capacidades de VELMA directamente al agente. |

### Schema de la Base de Datos

| Tabla | Ubicación | Qué guarda |
|-------|-----------|-------------|
| `issues_log` | `./VELMA/knowledge.db` | Errores resueltos, intentos fallidos y evidencias de éxito. |
| `reasoning_log` | `./VELMA/knowledge.db` | Resúmenes de sesión y tareas completadas. |
| `docs_index` | `./VELMA/knowledge.db` | Reglas de negocio y constraints divididas en "chunks". |
| `files_index` | `./VELMA/knowledge.db` | Resúmenes indexados de los archivos fuente del proyecto. |

---

## 🛠 Uso Manual (CLI Fallback)

Aunque los agentes usan MCP, los humanos (o agentes en entornos sin MCP) pueden interactuar con VELMA por consola.

### Búsqueda
```bash
# Búsqueda híbrida (texto + semántica)
python VELMA/search.py "error de base de datos" --table all
```

### Indexación
```bash
# Indexar la documentación del proyecto (carpeta docs/)
python VELMA/indexer.py --docs

# Indexar el código fuente (Python, JS, TS)
python VELMA/indexer.py --files
```

### Registro Manual
```bash
# Registrar un error resuelto
python VELMA/logger.py issue \
  --error "TypeError: innerHtml" \
  --resolution "Use innerHTML" \
  --approach "Case sensitivity fix" \
  --evidence "Logs del test"
```

---

## 📂 Estructura del Proyecto

VELMA es limpia y minimalista, diseñada para vivir silenciosamente dentro de tu repositorio.

```text
TuProyecto/
├── .env                 # Variables de tu proyecto
├── CLAUDE.md            # Instrucciones auto-generadas (HARD STOP)
├── GEMINI.md            # Instrucciones para Google
├── INSTRUCTIONS.md      # Instrucciones universales
├── src/                 # TU código
└── VELMA/               # El cerebro encapsulado
    ├── mcp_server.py    # El servidor Model Context Protocol
    ├── search.py        # Motor de búsqueda
    ├── logger.py        # Herramienta de escritura
    ├── indexer.py       # Lector de archivos
    ├── kb_utils.py      # Conexión con Ollama
    ├── setup_kb.py      # Creador de tablas
    ├── knowledge.db     # (Ignorado por Git) La memoria SQLite
    └── skills/velma/SKILL.md # Manifiesto estándar de la habilidad
```

## 📜 Licencia

MIT
