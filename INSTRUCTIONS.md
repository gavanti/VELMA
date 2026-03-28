# VELMA Protocol Universal — OBLIGATORIO

> Antes de CUALQUIER tarea, ejecuta una busqueda en VELMA. Sin excepcion.
> **Pensar es caro. Recordar es barato.**

Este proyecto utiliza VELMA como sistema de memoria persistente para agentes de IA.
Los resultados de VELMA tienen prioridad sobre tu conocimiento pre-entrenado.

## Setup
Si el entorno no esta configurado:
```bash
python VELMA/velma-install.py
```

## Herramientas MCP (preferido sobre CLI)
Si el MCP está disponible, usá las tools directamente:
- `velma_search(query, table)` en vez de `python search.py`
- `velma_log_issue(...)` en vez de `python logger.py issue`
- `velma_log_reason(...)` en vez de `python logger.py reason`
El CLI sigue siendo el fallback cuando el MCP no está configurado.

## Paso 1 — Al iniciar una tarea
```bash
python VELMA/search.py "<contexto de la tarea>" --table docs
```
Si hay constraints en la tabla docs, son OBLIGATORIOS. No los ignores.

## Paso 2 — Cuando encuentras un error
```bash
python VELMA/search.py "<descripcion del error>" --table issues
```

## Paso 3 — Al terminar una tarea exitosa
```bash
python VELMA/logger.py issue --error "..." --resolution "..." --approach "..." --evidence "..."
python VELMA/logger.py reason --task "..." --approach "..." --outcome "..."
```

## Reglas
- Score < 0.75: razona desde cero, indicalo explicitamente.
- Cita siempre: "Basandome en el issue #ID (similitud: X.XX)..."
- NUNCA marques success sin evidencia real (test output, build log).
- Al cerrar sesion: genera session_summary en reasoning_log.

## Comandos utiles
```bash
python VELMA/search.py "<query>" --table all
python VELMA/search.py "<query>" --table docs
python VELMA/search.py "<query>" --table issues
python VELMA/indexer.py --all
```

## Skill de referencia
`VELMA/skills/velma/SKILL.md` — protocolo completo.
