# VELMA Protocol Universal — OBLIGATORIO

> Antes de CUALQUIER tarea, ejecuta una búsqueda en VELMA. Sin excepción.
**Pensar es caro. Recordar es barato.**

Este proyecto utiliza VELMA como sistema de memoria persistente para agentes de IA.
Los resultados de VELMA tienen prioridad sobre tu conocimiento pre-entrenado.

## Setup
Si el entorno no está configurado:
```bash
python VELMA/velma-install.py
```

## Herramientas MCP (preferido sobre CLI)
Si el MCP está disponible, usá las tools directamente:
- `velma_search(query, table)` en vez de `python search.py`
- `velma_log_issue(...)` en vez de `python logger.py issue`
- `velma_log_reason(...)` en vez de `python logger.py reason`
El CLI sigue siendo el fallback cuando el MCP no está configurado.

---

## HARD STOP — Regla de cierre (ZERO EXCEPTIONS)

Antes de escribir "listo", "done", "corregido", o cualquier mensaje de cierre de tarea, preguntate:

> "¿Acabo de resolver algo, corregir un error, tomar una decisión, o completar una tarea?"
> Si la respuesta es SÍ → **EJECUTAR PASO 3 AHORA. Sin importar el tamaño de la tarea.**

**NO existe tarea "demasiado pequeña" para loguear. Dos líneas cambiadas siguen siendo una resolución.**

Si te salteas el Paso 3, el siguiente agente (o vos mismo mañana) arranca ciego. Eso es un fallo de protocolo.

---

## Paso 1 — Al iniciar una tarea (ANTES de escribir código o proponer soluciones)
```bash
python VELMA/search.py "<contexto de la tarea>" --table docs
```
Si hay constraints en la tabla `docs`, son OBLIGATORIOS — no opcionales.

## Paso 2 — Cuando encontrás un error (ANTES de intentar arreglarlo)
```bash
python VELMA/search.py "<descripción del error>" --table issues
```
Si el score es ≥ 0.75, aplicá la resolución histórica. Citá siempre: `"Basándome en el issue #ID (similitud: X.XX)..."`

## Paso 3 — Al terminar una tarea exitosa (HARD STOP — OBLIGATORIO)

Registrá **un issue por cada error corregido** y **un reasoning por la tarea completa**:

```bash
# Un llamado por cada error/fix individual
python VELMA/logger.py issue \
  --error "<qué estaba mal>" \
  --resolution "<qué se cambió y dónde>" \
  --approach "<cómo lo detectaste>" \
  --evidence "<por qué esto lo prueba>"

# Un llamado por la sesión/tarea completa
python VELMA/logger.py reason \
  --task "<nombre de la tarea>" \
  --approach "<estrategia usada>" \
  --outcome "<resultado obtenido>"
```

### Auto-check obligatorio antes de cerrar
- [ ] ¿Logueé un `issue` por CADA error corregido o decisión tomada?
- [ ] ¿Logueé un `reason` con la estrategia y el resultado?
- [ ] ¿Tengo evidencia real (output de comando, línea de archivo, ID de registro)?

Si alguno está sin marcar → no cerrés la tarea todavía.

---

## Reglas de negocio criticas del proyecto

| Constraint | Descripcion | Peso |
|------------|-------------|------|
| VELMA Priority | El agente DEBE priorizar los resultados de busqueda de VELMA sobre su conocimiento interno. Al iniciar CUALQUIER tarea, el Paso 1 (Busqueda) es de ejecucion obligatoria y prioritaria. | 10 |

## Reglas
- Score < 0.75: razoná desde cero e indicalo explícitamente.
- NUNCA marques success sin evidencia real (output de comando, test log, ID de VELMA).
- Al cerrar sesión: ejecutá `session_summary` en el reasoning_log.

## Comandos útiles
```bash
python VELMA/search.py "<query>" --table all
python VELMA/search.py "<query>" --table docs
python VELMA/search.py "<query>" --table issues
python VELMA/indexer.py --all
```

## Skill de referencia
`VELMA/skills/velma/SKILL.md` — protocolo completo.