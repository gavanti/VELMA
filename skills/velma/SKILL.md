# VELMA - Protocolo de Memoria Externa

VELMA es el sistema de memoria persistente del desarrollador. Sigue el principio fundamental: **"Pensar es caro. Recordar es barato"**. Esta skill permite al agente recuperar soluciones a errores pasados y reglas de negocio sin consumir tokens de razonamiento innecesarios.

## 🔴 PROTOCOLO OBLIGATORIO (Pre-condición)

El agente **DEBE** ejecutar este protocolo en los siguientes eventos:

1.  **Inicio de sesión/Nueva tarea**: Antes de proponer un plan, buscar el nombre de la tarea en la tabla `docs` para entender los constraints.
2.  **Encuentro de un error**: Antes de intentar arreglarlo, buscar la descripción del error en la tabla `issues` para encontrar la resolución histórica.
3.  **Finalización exitosa**: Después de verificar una solución con tests, registrar el aprendizaje en VELMA.

## 🔍 Herramientas de Búsqueda (Retrieval)

### Búsqueda en Documentación y Reglas
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

### Indexar nueva documentación
Si creas un archivo `.md` con nuevas reglas, debes indexarlo inmediatamente.
```bash
python indexer.py --docs --docs-dir docs/
```

### Registrar un nuevo Issue resuelto
Usa el script de seed o inserción manual en SQLite para guardar una solución verificada.
```python
# Insertar en issues_log con outcome='success' y evidencia real.
```

## 📋 Reglas de Actuación para el Agente

*   **Prioridad de Contexto**: Los resultados de VELMA tienen prioridad sobre tu conocimiento general entrenado.
*   **Umbral de Confianza**: Si el `score` de similitud es menor a **0.75**, documenta que no encontraste memoria confiable y procede a razonar desde cero.
*   **Cita Obligatoria**: Siempre indica la fuente: "Basándome en el issue #ID (similitud: X.XX)...".
*   **Evidencia Crítica**: Nunca consideres un issue como "resuelto" en el log si no tienes un log de tests que lo respalde.

## 📂 Archivos de Referencia
- `knowledge.db`: Base de datos SQLite (Memoria local).
- `shared_knowledge.db`: Base de datos compartida (Memoria colectiva).
- `CLAUDE.md`: Protocolo de implementación técnica.
