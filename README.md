# VELMA - Knowledge Base Persistente para Agentes de IA

Sistema de memoria persistente para agentes de IA. Convierte razonamiento en recuperación, eliminando la repetición de errores y anclando al agente en las reglas de negocio reales de tu proyecto.

> **Principio clave**: *Pensar es caro. Recordar es barato.*

## ⚡ Instalación Rápida (Un solo Enter)

Si estás en Windows (PowerShell), ejecuta:
```powershell
irm https://raw.githubusercontent.com/tu-usuario/velma/main/install.ps1 | iex
```

---

## Propósito

Cada sesión de un agente de IA empieza desde cero. Este sistema resuelve eso con una base de conocimiento persistente que el agente consulta antes de razonar.

**Beneficios:**
- Menos tokens gastados por sesión
- Cero repetición de errores ya resueltos
- Ancla al agente en las reglas de negocio reales de tu proyecto

## Arquitectura

### Stack Tecnológico

| Componente | Tecnología | Propósito |
|------------|------------|-----------|
| Base de datos | SQLite local | Base personal de cada dev, sin servidor |
| Full-text search | FTS5 | B squeda exacta por palabras clave |
| Embeddings | paraphrase-multilingual-MiniLM-L12-v2 | B squeda sem ntica (420MB, nativo ES/EN) |
| Web panel | Flask | Panel para revisar y verificar entradas |
| Sync | GitHub Actions | Merge automático en cada PR |

### Separación Personal vs. Compartido

| Tabla | Ubicación | Visibilidad |
|-------|-----------|-------------|
| `files_index` | Solo local | Dev y su agente |
| `functions_index` | Solo local | Dev y su agente |
| `issues_log` (raw) | Solo local | Solo el dev |
| `issues_log` (verified) | Local + shared | Todo el equipo |
| `reasoning_log` | Local + shared | Todo el equipo |
| `docs_index` | Local + shared | Todo el equipo |

## Schema de la Base de Datos

### `issues_log` - Errores y Resoluciones

```sql
CREATE TABLE issues_log (
    id INTEGER PRIMARY KEY,
    error TEXT NOT NULL,           -- Descripción del error
    resolution TEXT,               -- Cómo se resolvió
    context TEXT,                  -- Dónde ocurrió (archivo:función)
    approach TEXT,                 -- Razonamiento detrás de la solución
    attempts TEXT,                 -- JSON: intentos fallidos
    tags TEXT,                     -- JSON: etiquetas
    outcome TEXT,                  -- unverified|success|failed|human_confirmed
    evidence TEXT,                 -- Output que prueba que funcionó
    status TEXT,                   -- raw → verified → merged → archived
    fingerprint TEXT UNIQUE,       -- Hash MD5 para deduplicar
    embedding BLOB,                -- Vector de 384 dimensiones
    verified_by TEXT,
    owner TEXT,
    created_at DATETIME,
    expires_at DATETIME            -- Revisión obligatoria (90 días)
);
```

### `docs_index` - Documentación y Reglas

```sql
CREATE TABLE docs_index (
    id INTEGER PRIMARY KEY,
    doc_source TEXT,               -- Nombre del archivo origen
    chunk_title TEXT,              -- Título del concepto
    chunk_body TEXT,               -- Contenido completo
    chunk_type TEXT,               -- constraint|rule|procedure|concept|example
    order_in_doc INTEGER,
    embedding BLOB,                -- Vector para búsqueda semántica
    hash TEXT,
    verified BOOLEAN,
    applies_to TEXT,               -- JSON: proyectos a los que aplica
    updated_at DATETIME
);
```

## Instalación

```bash
# 1. Clonar el repositorio
git clone <url> velma-kb && cd velma-kb

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar setup (crea knowledge.db con el schema completo)
python setup_kb.py

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env: PROJECT_NAME, DEV_NAME, etc.

# 5. Agregar documentación de tu proyecto a docs/
# (archivos .md con reglas de negocio, constraints, procedimientos)
python indexer.py --docs --docs-dir docs/

# 6. Indexar código fuente (opcional)
python indexer.py --files

# 7. Iniciar panel web
python search.py --web
```

## Uso

### Búsqueda desde CLI

```bash
# Buscar en toda la base de conocimiento
python search.py "error de conexión"

# Buscar solo en documentación
python search.py "reglas de negocio" --table docs

# Buscar solo en issues
python search.py "timeout en API" --table issues

# Output en JSON (para integración con agentes)
python search.py "autenticación" --json
```

### Panel Web

```bash
python search.py --web --port 5000
# Abrir http://localhost:5000
```

### Indexación

```bash
# Indexar todo el proyecto
python indexer.py --all

# Solo archivos de código (.py, .js, .ts)
python indexer.py --files

# Solo documentación (.md)
python indexer.py --docs --docs-dir docs/

# Poblar desde JSON externo (generado por agente o script)
python tests/seed_db.py datos.json --db knowledge.db
```

### Merge (Sincronización entre devs)

```bash
# Simular merge (dry-run)
python merge_knowledge.py --dry-run

# Ejecutar merge
python merge_knowledge.py --merged-by "tu-nombre"

# Ver conflictos pendientes
python merge_knowledge.py --conflicts

# Resolver conflicto
python merge_knowledge.py --resolve 123 --resolution "Usar versión A"
```

## Ciclo de Vida de una Entrada

```
raw → verified → merged → archived
```

| Estado | Descripción |
|--------|-------------|
| `raw` | Agente escribió sin revisión. Otros agentes NO la usan. |
| `verified` | Un dev la revisó y aprobó. Lista para merge. |
| `merged` | Incluida en el shared. Referencia al shared_id. |
| `archived` | Obsoleta. Solo un humano puede archivar. |

**Regla de oro**: La única operación destructiva es `archived`, y solo la ejecuta un humano.

## Búsqueda Híbrida (RRF)

El sistema combina dos señales usando **Reciprocal Rank Fusion**:

1. **FTS5**: Encuentra matches exactos de palabras clave
2. **Embeddings**: Encuentra matches sem nticos (paraphrase-multilingual-MiniLM-L12-v2, 384 dims)

### Pesos por Tipo de Chunk

| Tipo | Peso | Uso |
|------|------|-----|
| `constraint` | 10 | Reglas duras, nunca ignoradas |
| `rule` | 8 | Políticas de negocio |
| `procedure` | 7 | Cómo hacer algo |
| `concept` | 5 | Definiciones |
| `example` | 3 | Ilustraciones |

## Anti-Alucinación

1. **Score mínimo**: Si similitud < 0.75, el agente razona desde cero
2. **Solo verified**: El agente ignora entradas `raw` y `archived`
3. **Citar fuente**: Cada uso del KB debe indicar ID y score
4. **Expiración**: 90 días por defecto, configurable
5. **Constraints primero**: Peso 10, nunca ignoradas

## Tests

```bash
# Suite completa (192 tests + agente económico)
python run_all_tests.py

# Solo tests unitarios (rápido, ~0.4s)
python run_all_tests.py --fast

# Solo el agente económico batch
python run_all_tests.py --agent-only --db knowledge.db

# Con coverage
python run_all_tests.py --coverage
```

## Estructura del Proyecto

```
velma-kb/
├── setup_kb.py              # Fase 1: Setup inicial (crea DB)
├── indexer.py               # Fase 2: Indexación de archivos y docs
├── search.py                # Fase 3: Busqueda hibrida + panel web
├── merge_knowledge.py       # Fase 4: Merge y deduplicacion
├── kb_utils.py              # Utilidades: hash, embeddings, similarity
├── run_all_tests.py         # Runner de tests
├── requirements.txt         # Dependencias de produccion
├── requirements-test.txt    # Dependencias de testing
├── CLAUDE.md                # Protocolo para agentes de IA
├── .env.example             # Variables de entorno (template)
├── docs/                    # Tus documentos .md (reglas, constraints)
├── templates/               # Templates del panel web Flask
├── tests/
│   ├── unit/                # Tests unitarios (hash, FTS5, utils)
│   ├── integration/         # Tests de integracion (indexer, search, merge)
│   ├── fixtures/            # Generador de datos sinteticos
│   ├── agent_tester.py      # Agente economico batch
│   └── seed_db.py           # Poblar DB desde JSON externo
└── .github/
    └── workflows/
        └── merge-knowledge.yml
```

## GitHub Action

El merge automático corre en cada PR mergeado a `main` o `develop`:

```yaml
on:
  pull_request:
    types: [closed]
    branches: [main, develop]
```

### Deduplicación en el Merge

| Tipo | Detección | Acción |
|------|-----------|--------|
| Exacto | Hash MD5 idéntico | Descarta silenciosamente |
| Semantico (>0.92) | Similitud vectorial | Enriquece entrada existente |
| Conflicto (0.85-0.92) | Similitud media | Marca `needs_review` |

## Licencia

MIT
