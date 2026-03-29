# VELMA - Protocolo de Memoria Externa

VELMA es el sistema de memoria persistente del desarrollador. Sigue el principio fundamental: "Pensar es caro. Recordar es barato". Esta skill permite al agente recuperar soluciones a errores pasados y reglas de negocio sin consumir tokens de razonamiento innecesarios.

## PROTOCOLO OBLIGATORIO (Pre-condicion)

El agente DEBE ejecutar este protocolo en los siguientes eventos:

1.  Inicio de sesion/Nueva tarea: Antes de proponer un plan, buscar el nombre de la tarea en la tabla docs para entender los constraints.
2.  Encuentro de un error: Antes de intentar arreglarlo, buscar la descripcion del error en la tabla issues para encontrar la resolucion historica.
3.  Finalizacion exitosa: Despues de verificar una solucion con tests, registrar el aprendizaje en VELMA.

## AUTO-HOOKS (Interceptacion Automatica)

VELMA instala hooks en el shell que interceptan comandos como "claude", "gemini" y "opencode".
- Si el comando se ejecuta sin --no-velma, el sistema inyecta automaticamente el contexto de busqueda en la variable de entorno VELMA_CONTEXT.
- El agente DEBE leer esta variable al iniciar la sesion para obtener memoria historica relevante.

## Herramientas de Busqueda (Retrieval)

### MCP Tools (Recomendado)
- `velma_search(query, table)`

### Búsqueda en Documentación y Reglas (CLI Fallback)
Usa esto para entender el "QUÉ" y el "CÓMO" del proyecto actual.
```bash
python search.py "<contexto o tarea>" --table docs
```

### Búsqueda en Historial de Errores (Issues)
Usa esto para evitar resolver problemas que ya fueron solucionados anteriormente.
```bash
python search.py "<descripción del error>" --table issues
```

## 🛠️ Herramientas de Escritura (Memory Storage)

### MCP Tools (Recomendado)
- `velma_log_issue(error, resolution, approach, evidence, context)`
- `velma_log_reason(task, approach, outcome)`
- `velma_log_discovery(title, content, source)`

### Indexar nueva documentación (CLI)
Si creas un archivo `.md` con nuevas reglas, debes indexarlo inmediatamente.
```bash
python indexer.py --docs --docs-dir docs/
```

### Registrar un nuevo Issue resuelto (CLI Fallback)
```bash
python VELMA/logger.py issue --error "..." --resolution "..." --approach "..." --evidence "..."
```

## 📋 Reglas de Actuación para el Agente

*   **Prioridad de Contexto**: Los resultados de VELMA tienen prioridad sobre tu conocimiento general entrenado.
*   **Umbral de Confianza**: Si el `score` de similitud es menor a **0.75**, documenta que no encontraste memoria confiable y procede a razonar desde cero.
*   **Cita Obligatoria**: Siempre indica la fuente: "Basándome en el issue #ID (similitud: X.XX)...".
*   **Evidencia Crítica**: Nunca consideres un issue como "resuelto" en el log si no tienes un log de tests que lo respalde.

## 📂 Archivos de Referencia
- `knowledge.db`: Base de datos SQLite (Memoria local).
- `shared_knowledge.db`: Base de datos compartida (Memoria colectiva).
- `CLAUDE.md`: Instrucciones para Claude.
- `gemini.md`: Instrucciones para Gemini.
- `INSTRUCTIONS.md`: Instrucciones universales para cualquier agente.

