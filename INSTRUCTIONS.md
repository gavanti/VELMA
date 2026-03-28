# Repositorio VELMA - Instrucciones Universales para Agentes

Este repositorio utiliza el sistema de memoria persistente **VELMA**. Cualquier agente de IA (Claude, Gemini, GPT, etc.) que opere en este entorno debe adherirse al siguiente protocolo de memoria externa.

## Skill Principal
La lógica de interacción detallada se encuentra en: `skills/velma/SKILL.md`.

## Resumen del Protocolo Obligatorio

1.  **RECONOCE**: Tienes una memoria externa en `knowledge.db`.
2.  **RECUPERA**: Antes de proponer código o lógica, ejecuta `python search.py "<query>"`.
3.  **RECUERDA**: Prioriza los resultados de la base de datos sobre tu conocimiento pre-entrenado.
4.  **REGISTRA**: Guarda tus aciertos y errores corregidos en `issues_log`.

## Herramientas Disponibles
- `python search.py`: Motor de búsqueda híbrido (FTS5 + Vectorial).
- `python indexer.py`: Para actualizar la base de conocimientos.
- `python merge_knowledge.py`: Para sincronizar con el equipo.

---
"Pensar es caro. Recordar es barato."
