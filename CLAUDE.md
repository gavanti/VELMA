# VELMA Knowledge Base - Protocolo para Agentes

> **SKILL CARGADA**: `skills/velma/SKILL.md` (Obligatorio revisar antes de actuar)

## Instalación y Setup
Si el entorno no está configurado, ejecuta el instalador TUI:
```bash
python velma-install.py
```

## Herramientas MCP (preferido sobre CLI)
Si el MCP está disponible, usá las tools directamente:
- `velma_search(query, table)` en vez de `python search.py`
- `velma_log_issue(...)` en vez de `python logger.py issue`
- `velma_log_reason(...)` en vez de `python logger.py reason`
El CLI sigue siendo el fallback cuando el MCP no está configurado.

## Antes de empezar cualquier tarea

1. Ejecuta `search.py` con el contexto de la tarea. **ESTO NO ES OPCIONAL**.
2. Si hay constraints relevantes en la tabla `docs`, son obligatorios — no las ignores.
3. Si hay issues similares resueltos, úsalos como punto de partida prioritario.

```bash
# Ejemplo: Buscar información relevante antes de empezar
# VELMA soporta búsquedas bilingües (ES/EN)
python search.py "conexión base de datos" --table docs
```

## Cuando encuentras un error

1. **Busca en issues_log** antes de intentar resolver
   ```bash
   python search.py "<descripción del error>" --table issues
   ```

2. **Registra cada intento fallido** en `attempts[]`

3. **Solo marca `outcome='success'` con evidencia real** (test output, build log)

4. **NUNCA marques success porque el código "se ve correcto"**

### Ejemplo de registro de conocimiento (Logger):

El agente **DEBE** usar `logger.py` para guardar nuevos aprendizajes:

```bash
# Registrar un error resuelto
python VELMA/logger.py issue \
  --error "Descripción del error" \
  --resolution "Solución técnica" \
  --approach "Razonamiento" \
  --evidence "Logs del test"

# Registrar un proceso o tarea finalizada
python VELMA/logger.py reason \
  --task "Nombre de la tarea" \
  --approach "Pasos realizados" \
  --outcome "Resultado final"
```

Los registros entran como `raw` y solo serán visibles para otros agentes después de que un humano los verifique en el dashboard.

## Al resolver un error

```python
# Actualizar el issue con la resolución
cursor.execute("""
    UPDATE issues_log
    SET resolution = ?,
        approach = ?,
        outcome = 'success',
        evidence = ?,
        status = 'verified'
    WHERE id = ?
""", (
    "<descripción de la solución>",
    "<razonamiento: por qué ocurrió y por qué esta solución funciona>",
    "Test: <nombre_del_test> PASSED (N/N)",
    issue_id
))
```

## Al procesar archivos

1. **Verifica el hash en files_index antes de leer**

```python
cursor.execute("SELECT hash FROM files_index WHERE path = ?", (file_path,))
result = cursor.fetchone()

if result:
    stored_hash = result[0]
    current_hash = compute_file_hash(open(file_path, 'rb').read())

    if stored_hash == current_hash:
        # Usar el summary guardado — no releas el archivo
        cursor.execute("SELECT summary FROM files_index WHERE path = ?", (file_path,))
        summary = cursor.fetchone()[0]
    else:
        # El archivo cambió — reprocesar
        pass
```

2. **Si el hash no cambió, usa el summary guardado** — no releas el archivo

## Al cerrar la sesión

**Genera session_summary en reasoning_log — esto NO es opcional**

```python
cursor.execute("""
    INSERT INTO reasoning_log (task, approach, outcome, status, owner)
    VALUES (?, ?, ?, 'raw', 'claude')
""", (
    "<descripción de la tarea completada>",
    """
    1. <paso 1 que se realizó>
    2. <paso 2 que se realizó>
    3. <resultado final>
    """,
    "<outcome: qué se logró y con qué evidencia>"
))
```

## Reglas de negocio críticas del proyecto

<!-- PERSONALIZAR: Agrega aquí las constraints específicas de tu proyecto.
     Usa el formato de tabla. El peso indica prioridad (10 = máximo). -->

| Constraint | Descripción | Peso |
|------------|-------------|------|
| _(agrega tus reglas aquí)_ | _(descripción)_ | _(1-10)_ |

> Las reglas de esta tabla se cargan como docs de tipo `constraint` en docs_index
> via `python indexer.py --docs`. Agrégalas a tu archivo de documentación
> y ejecuta el indexer para que el agente las encuentre automáticamente.

## Score de confianza mínimo

Si la similitud del resultado recuperado es menor a **0.75**, el agente no lo usa como contexto. Razona desde cero.

## Citar siempre la fuente

Cada vez que uses una entrada del knowledge base, indica el ID y el score de similitud:

```
Basándome en el issue #42 (similitud: 0.89), el error de conexión
se resuelve agregando retry con backoff...
```

## Expiración automática

Las entradas tienen `expires_at = 90 días` por defecto. Advierte al usarlas si están próximas a expirar.

## Comandos útiles

```bash
# Buscar en toda la base de conocimiento
python search.py "<query>" --all

# Buscar solo en documentación
python search.py "<query>" --table docs

# Buscar solo en issues
python search.py "<query>" --table issues

# Iniciar panel web
python search.py --web

# Indexar archivos del proyecto
python indexer.py --all

# Indexar solo documentación
python indexer.py --docs --docs-dir docs/

# Mergear conocimiento verificado (dry-run)
python merge_knowledge.py --dry-run

# Mergear conocimiento verificado (live)
python merge_knowledge.py

# Poblar DB desde JSON externo (ej: datos generados por otro agente)
python tests/seed_db.py <archivo.json> --db knowledge.db
```
