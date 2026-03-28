# Instrucciones para Gemini (Protocolo VELMA)

> **SKILL OBLIGATORIA**: `skills/velma/SKILL.md`

## Instalación y Setup
Antes de empezar, asegúrate de tener el entorno listo con la TUI:
```bash
python velma-install.py
```

## Protocolo de Interacción

1.  **Búsqueda Inicial**: Ante cualquier nueva tarea o pregunta sobre el proyecto, ejecuta:
    ```bash
    python search.py "<contexto de la tarea>" --table docs
    ```
2.  **Manejo de Errores**: Si encuentras un error técnico, antes de proponer una solución, busca si ya ha sido resuelto:
    ```bash
    python search.py "<error detectado>" --table issues
    ```
3.  **Registro de Conocimiento**: Al finalizar una tarea exitosa, guarda tu razonamiento y la solución técnica en la base de datos (ver `SKILL.md` para comandos de inserción).

## Reglas de Oro
- **Pensar es caro. Recordar es barato.**
- No asumas reglas de negocio; recupéralas de VELMA.
- Si el score de similitud es < 0.75, indícalo y procede con cautela.
- Cita siempre el ID del issue o documento consultado.
