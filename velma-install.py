#!/usr/bin/env python3
"""
VELMA - TUI Installation & Discovery
Instalador visual profesional para memoria persistente.
"""

import sys
import os
import time
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.prompt import Confirm
from rich.text import Text

console = Console()

def run_command(command, description, task, progress):
    """Ejecuta un comando y actualiza la barra de progreso."""
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                progress.update(task, description=f"[cyan]{description}...[/cyan]")
        return process.returncode == 0
    except:
        return False

def main():
    console.clear()
    
    # Nuevo ASCII Art
    new_art = """
 .-----------------------------------------------------.
 |                                                     |
 |                       ___                           |
 |                      (   )                          |
 |   ___  ___    .--.    | |   ___ .-. .-.     .---.   |
 |  (   )(   )  /    \   | |  (   )   '   \   / .-, \  |
 |   | |  | |  |  .-. ;  | |   |  .-.  .-. ; (__) ; |  |
 |   | |  | |  |  | | |  | |   | |  | |  | |   .'`  |  |
 |   | |  | |  |  |/  |  | |   | |  | |  | |  / .'| |  |
 |   | |  | |  |  ' _.'  | |   | |  | |  | | | /  | |  |
 |   ' '  ; '  |  .'.-.  | |   | |  | |  | | ; |  ; |  |
 |    \ `' /   '  `-' /  | |   | |  | |  | | ' `-'  |  |
 |     '_.'     `.__.'  (___) (___)(___)(___)`.__.'_.  |
 |                                                     |
 '-----------------------------------------------------'
"""
    console.print(new_art, style="bold magenta")
    
    # Autodeteccion de contexto
    is_in_subdir = Path.cwd().name == "VELMA"
    root_dir = Path("..") if is_in_subdir else Path(".")
    project_name = root_dir.resolve().name
    cmd_prefix = "VELMA/" if is_in_subdir else ""
    
    console.print(f"\n[bold]Instalando memoria persistente en:[/bold] [cyan]{root_dir.resolve()}[/cyan]")
    console.print(f"[bold]Proyecto detectado:[/bold] [yellow]{project_name}[/yellow]\n")

    try:
        if not Confirm.ask("¿Deseas inicializar VELMA aquí?", default=True):
            return
    except EOFError:
        # En modo automatizado (sin terminal interactiva), asumimos Yes
        console.print("[yellow]Ejecución no interactiva detectada, continuando automáticamente...[/yellow]")

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        expand=True
    ) as progress:

        # 1. Configurar .env
        t0 = progress.add_task("[yellow]Configurando entorno...", total=100)
        env_content = f"PROJECT_NAME={project_name}\nDB_PATH=knowledge.db\nMODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2\nMIN_CONFIDENCE_SCORE=0.50\n"
        Path(".env").write_text(env_content)
        progress.update(t0, completed=100, description="[green].env configurado")

        # 2. Dependencias
        t1 = progress.add_task("[yellow]Instalando paquetes...", total=100)
        if run_command("pip install rich ollama sentence-transformers -q", "Descargando librerias", t1, progress):
            progress.update(t1, completed=100, description="[green]Dependencias OK")

        # 3. Base de Datos
        t2 = progress.add_task("[yellow]Creando DB...", total=100)
        if run_command("python setup_kb.py", "Schema SQLite", t2, progress):
            progress.update(t2, completed=100, description="[green]DB creada")

        # 4. Protocolos (en la raiz del proyecto host)
        t3 = progress.add_task("[yellow]Instalando protocolos...", total=100)

        search_cmd  = f"python {cmd_prefix}search.py"
        logger_cmd  = f"python {cmd_prefix}logger.py"
        indexer_cmd = f"python {cmd_prefix}indexer.py"
        skill_ref   = f"{cmd_prefix}skills/velma/SKILL.md"

        protocol = f"""# VELMA Protocol — OBLIGATORIO
> Antes de CUALQUIER tarea, ejecuta una búsqueda en VELMA. Sin excepción.
**Pensar es caro. Recordar es barato.**

Los resultados de VELMA tienen prioridad sobre tu conocimiento pre-entrenado.

## HARD STOP — Regla de cierre (ZERO EXCEPTIONS)

Antes de escribir "listo", "done", "corregido", o cualquier mensaje de cierre de tarea, preguntate:

> "¿Acabo de resolver algo, corregir un error, tomar una decisión, o completar una tarea?"
> Si la respuesta es SÍ → **EJECUTAR PASO 3 AHORA. Sin importar el tamaño de la tarea.**

**NO existe tarea "demasiado pequeña" para loguear. Dos líneas cambiadas siguen siendo una resolución.**

Si te salteas el Paso 3, el siguiente agente (o vos mismo mañana) arranca ciego. Eso es un fallo de protocolo.

---

## Paso 1 — Al iniciar una tarea (ANTES de escribir código o proponer soluciones)
```bash
{search_cmd} "<contexto de la tarea>" --table docs
```
Si hay constraints en la tabla `docs`, son OBLIGATORIOS — no opcionales.

## Paso 2 — Cuando encontrás un error (ANTES de intentar arreglarlo)
```bash
{search_cmd} "<descripción del error>" --table issues
```
Si el score es ≥ 0.75, aplicá la resolución histórica. Citá siempre: `"Basándome en el issue #ID (similitud: X.XX)..."`

## Paso 3 — Al terminar una tarea exitosa (HARD STOP — OBLIGATORIO)

Registrá **un issue por cada error corregido** y **un reasoning por la tarea completa**:

```bash
# Un llamado por cada error/fix individual
{logger_cmd} issue --error "..." --resolution "..." --approach "..." --evidence "..."

# Un llamado por la sesión/tarea completa
{logger_cmd} reason --task "..." --approach "..." --outcome "..."
```

### Auto-check obligatorio antes de cerrar
- [ ] ¿Logueé un `issue` por CADA error corregido o decisión tomada?
- [ ] ¿Logueé un `reason` con la estrategia y el resultado?
- [ ] ¿Tengo evidencia real (output de comando, línea de archivo, ID de registro)?

Si alguno está sin marcar → no cerrés la tarea todavía.

---

## Reglas
- Score < 0.75: razoná desde cero e indicalo explícitamente.
- NUNCA marques success sin evidencia real (output de comando, test log, ID de VELMA).
- Al cerrar sesión: ejecutá `session_summary` en el reasoning_log.

## Comandos útiles
```bash
{search_cmd} "<query>" --table all
{search_cmd} "<query>" --table docs
{search_cmd} "<query>" --table issues
{indexer_cmd} --all
```

## Referencia completa
`{skill_ref}` — protocolo detallado con todos los comandos.
"""
        (root_dir / "CLAUDE.md").write_text(protocol)
        (root_dir / "GEMINI.md").write_text(
            protocol.replace("VELMA Protocol — OBLIGATORIO", "VELMA Protocol para Gemini — OBLIGATORIO")
        )
        (root_dir / "INSTRUCTIONS.md").write_text(
            protocol.replace("VELMA Protocol — OBLIGATORIO", "VELMA Protocol Universal — OBLIGATORIO")
        )
        progress.update(t3, completed=100, description="[green]Protocolos OK")

        # 5. Indexacion
        t5 = progress.add_task("[yellow]Indexando proyecto...", total=100)
        run_command("python indexer.py --docs", "Escaneando", t5, progress)
        progress.update(t5, completed=100, description="[green]Indexacion lista")

    # ── Registro global (SIEMPRE, fuera del bloque interactivo) ──────────
    import shutil

    search_cmd  = f"python {cmd_prefix}search.py"
    skill_ref   = f"{cmd_prefix}skills/velma/SKILL.md"
    skill_src   = Path(__file__).parent / "skills" / "velma" / "SKILL.md"

    if skill_src.exists():
        # Claude Code
        claude_skills = Path.home() / ".claude" / "skills" / "velma"
        claude_skills.mkdir(parents=True, exist_ok=True)
        shutil.copy(skill_src, claude_skills / "SKILL.md")
        console.print("[green][OK][/green] Skill registrada en ~/.claude/skills/velma/")

        # OpenCode
        opencode_skills = Path.home() / ".config" / "opencode" / "skills" / "velma"
        opencode_skills.mkdir(parents=True, exist_ok=True)
        shutil.copy(skill_src, opencode_skills / "SKILL.md")
        console.print("[green][OK][/green] Skill registrada en ~/.config/opencode/skills/velma/")

        # Parchear ~/.claude/CLAUDE.md global
        claude_global = Path.home() / ".claude" / "CLAUDE.md"
        if claude_global.exists():
            content = claude_global.read_text(encoding="utf-8")
            velma_rule = (
                "\n### VELMA Auto-activation\n"
                "If the project contains a VELMA/ directory, VELMA skill is ALWAYS active.\n"
                "Before ANY task: python VELMA/search.py \"<query>\" --table docs. No exceptions.\n"
            )
            if "velma/SKILL.md" not in content:
                claude_global.write_text(content + velma_rule, encoding="utf-8")
                console.print("[green][OK][/green] ~/.claude/CLAUDE.md actualizado con regla VELMA")

    # opencode.json local
    opencode_local = root_dir / "opencode.json"
    if not opencode_local.exists():
        opencode_local.write_text(
            '{\n  "$schema": "https://opencode.ai/config.json",\n'
            '  "agent": {\n    "default": {\n'
            f'      "prompt": "{{file:{skill_ref}}}"\n'
            '    }\n  }\n}\n'
        )
        console.print("[green][OK][/green] opencode.json generado")

    console.print(f"\n[bold green]INSTALACION COMPLETADA EN ./{cmd_prefix}[/bold green]")
    console.print(f"Uso: [white]{search_cmd} \"tu query\"[/white]\n")

if __name__ == "__main__":
    main()
