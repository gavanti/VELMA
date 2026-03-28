# GAVANTI - Knowledge Base Persistente para Agentes de IA

Sistema de memoria persistente para agentes de IA del equipo RepoVG. Convierte razonamiento en recuperación, eliminando la repetición de errores y anclando al agente en las reglas de negocio reales.

> **Principio clave**: *Pensar es caro. Recordar es barato.*

## 🎯 Propósito

Nuestro equipo de 5 desarrolladores usa agentes de IA en el flujo diario. El problema: cada sesión empieza desde cero. Este sistema resuelve eso con una base de conocimiento persistente que el agente consulta antes de razonar.

**Beneficios:**
- Menos tokens gastados por sesión
- Cero repetición de errores ya resueltos
- Ancla al agente en las reglas de negocio reales (Chakana, RepoVG)

## 🏗️ Arquitectura

### Stack Tecnológico

| Componente | Tecnología | Propósito |
|------------|------------|-----------|
| Base de datos | SQLite local | Base personal de cada dev, sin servidor |
| Full-text search | FTS5 | Búsqueda exacta por palabras clave |
| Embeddings | all-MiniLM-L6-v2 | Búsqueda semántica (22MB, sin API) |
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

## 📊 Schema de la Base de Datos

### `issues_log` - Errores y Resoluciones

```sql
CREATE TABLE issues_log (
    id INTEGER PRIMARY KEY,
    error TEXT NOT NULL,           -- Descripción del error
    resolution TEXT,               -- Cómo se resolvió
    context TEXT,                  -- Dónde ocurrió
    approach TEXT,                 -- Razonamiento detrás
    attempts TEXT,                 -- JSON: intentos fallidos
    tags TEXT,                     -- JSON: etiquetas
    outcome TEXT,                  -- unverified|success|failed|human_confirmed
    evidence TEXT,                 -- Output que prueba que funcionó
    status TEXT,                   -- raw → verified → merged → archived
    fingerprint TEXT UNIQUE,       -- Hash MD5 para deduplicar
    embedding BLOB,                -- Vector de 384 dimensiones
    verified_by TEXT,              -- Dev que aprobó
    shared_id INTEGER,             -- ID en shared si fue mergeada
    owner TEXT,                    -- Dev que creó la entrada
    created_at DATETIME,
    verified_at DATETIME,
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
    order_in_doc INTEGER,          -- Posición en el documento
    embedding BLOB,                -- Vector para búsqueda semántica
    hash TEXT,                     -- Hash del doc
    verified BOOLEAN,              -- Solo verified entra al shared
    applies_to TEXT,               -- JSON: proyectos
    updated_at DATETIME
);
```

## 🚀 Instalación

```bash
# 1. Clonar o copiar el proyecto
cd gavanti-kb

# 2. Ejecutar setup (Fase 1)
python setup_kb.py

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Copiar configuración
cp .env.example .env
# Editar .env con tus variables

# 5. Indexar proyecto (Fase 2)
python indexer.py --all

# 6. Iniciar panel web (Fase 3)
python search.py --web
```

## 📖 Uso

### Búsqueda desde CLI

```bash
# Buscar en toda la base de conocimiento
python search.py "error de conexión"

# Buscar solo en documentación
python search.py "valor del Aurio" --table docs

# Buscar solo en issues
python search.py "Supabase RLS" --table issues

# Output en JSON
python search.py "autenticación" --json
```

### Panel Web

```bash
# Iniciar servidor
python search.py --web --port 5000

# Abrir en navegador
open http://localhost:5000
```

### Indexación

```bash
# Indexar todo
python indexer.py --all

# Indexar solo archivos
python indexer.py --files

# Indexar solo documentación
python indexer.py --docs --docs-dir docs/

# Indexar archivo específico
python indexer.py --files --target src/payments.py
```

### Merge (Sincronización)

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

## 🔄 Ciclo de Vida de una Entrada

```
raw → verified → merged → archived
```

| Estado | Descripción |
|--------|-------------|
| `raw` | Agente escribió sin revisión. Otros agentes NO la usan. |
| `verified` | Un dev la revisó y aprobó. Lista para merge. |
| `merged` | Incluida en el shared. Referencia al shared_id. |
| `archived` | Obsoleta. Solo humano puede archivar. |

**Regla de oro**: La única operación destructiva permitida es `archived`, y solo la ejecuta un humano.

## 🔍 Búsqueda Híbrida (RRF)

El sistema combina dos señales usando **Reciprocal Rank Fusion**:

1. **FTS5**: Encuentra matches exactos de palabras clave
2. **Embeddings**: Encuentra matches semánticos por similitud

### Pesos por Tipo de Chunk

| Tipo | Peso | Uso |
|------|------|-----|
| `constraint` | 10 | Reglas duras ("el Aurio vale exactamente $0.01") |
| `rule` | 8 | Políticas de negocio |
| `procedure` | 7 | Cómo hacer algo |
| `concept` | 5 | Definiciones |
| `example` | 3 | Ilustraciones |

## 🛡️ Mecanismos Anti-Alucinación

1. **Score de confianza mínimo**: Si similitud < 0.75, el agente no usa el resultado
2. **Solo entradas verified**: El agente ignora `raw` y `archived`
3. **Citar fuente**: Cada uso del KB debe indicar ID y score
4. **Expiración automática**: 90 días por defecto
5. **Constraints sobre todo**: Peso 10, nunca ignorados

## 📝 Para el Agente (CLAUDE.md)

Ver archivo `CLAUDE.md` para el protocolo completo que debe seguir el agente:

- Buscar antes de razonar
- Registrar cada intento fallido
- Solo marcar success con evidencia real
- Generar session_summary al cerrar

## 🔧 GitHub Action

El merge automático se ejecuta en cada PR mergeado:

```yaml
# .github/workflows/merge-knowledge.yml
on:
  pull_request:
    types: [closed]
    branches: [main, develop]
```

### Deduplicación en el Merge

| Tipo | Detección | Acción |
|------|-----------|--------|
| Exacto | Hash MD5 idéntico | Descarta silenciosamente |
| Semántico (>0.92) | Similitud vectorial | Enriquece entrada existente |
| Conflicto (0.85-0.92) | Similitud media | Marca `needs_review` |

## 📁 Estructura del Proyecto

```
gavanti-kb/
├── setup_kb.py              # Fase 1: Setup inicial
├── indexer.py               # Fase 2: Indexación
├── search.py                # Fase 3: Búsqueda + panel web
├── merge_knowledge.py       # Fase 4: Merge y sync
├── kb_utils.py              # Utilidades compartidas
├── CLAUDE.md                # Protocolo para agentes
├── requirements.txt         # Dependencias
├── .env.example             # Configuración de ejemplo
├── knowledge.db             # Base de datos local (gitignored)
├── shared_knowledge.db      # Base compartida (versionada)
├── templates/               # Templates del panel web
│   ├── base.html
│   ├── index.html
│   ├── search.html
│   └── issues.html
└── .github/
    └── workflows/
        └── merge-knowledge.yml
```

## 🤝 Contribución

1. Trabaja en tu `knowledge.db` local
2. Verifica las entradas importantes (`status = 'verified'`)
3. Haz PR
4. El GitHub Action mergea automáticamente
5. El equipo hace `git pull` y obtiene el nuevo conocimiento

## 📄 Licencia

Confidencial - Equipo RepoVG - Marzo 2026
