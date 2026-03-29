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

def _register_hooks(root_dir, progress, task):
    """Registra los hooks de VELMA en los perfiles de shell detectados."""
    root_path = Path(root_dir).resolve()
    hooks_dir = root_path / "hooks"
    
    # 1. Bash / Zsh
    bash_profile = Path.home() / ".bashrc"
    zsh_profile = Path.home() / ".zshrc"
    bash_hook_script = hooks_dir / "bash_hooks.sh"
    
    source_line = f"\n# VELMA Hooks\n[ -f \"{bash_hook_script}\" ] && source \"{bash_hook_script}\"\n"
    
    for profile in [bash_profile, zsh_profile]:
        if profile.exists():
            content = profile.read_text(errors='ignore')
            if str(bash_hook_script) not in content:
                with profile.open("a") as f:
                    f.write(source_line)
                progress.update(task, description=f"[cyan]Hook Bash registrado en {profile.name}")

    # 2. PowerShell
    # Intentar obtener la ruta del perfil de PowerShell
    try:
        ps_profile_path = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", "$PROFILE"], 
            text=True
        ).strip()
        
        if ps_profile_path:
            ps_profile = Path(ps_profile_path)
            ps_hook_script = hooks_dir / "powershell_hooks.ps1"
            ps_source_line = f"\n# VELMA Hooks\nif (Test-Path \"{ps_hook_script}\") {{ . \"{ps_hook_script}\" }}\n"
            
            if not ps_profile.parent.exists():
                ps_profile.parent.mkdir(parents=True, exist_ok=True)
                
            content = ""
            if ps_profile.exists():
                content = ps_profile.read_text(errors='ignore')
                
            if str(ps_hook_script) not in content:
                with ps_profile.open("a") as f:
                    f.write(ps_source_line)
                progress.update(task, description="[cyan]Hook PowerShell registrado")
    except:
        # Fallo silencioso si PowerShell no esta disponible o falla el comando
        pass

def main():
    console.clear()
    
    # Nuevo ASCII Art
    new_art = r"""
    ####################      ####################
  ########################  ########################
  ##                    ##  ##                    ##
  ##  ################  ##  ##  ################  ##
  ##  ################  ##==##  ################  ##
  ##  ################  ######  ################  ##
  ##  ################  ##  ##  ################  ##
  ##                    ##  ##                    ##
  ########################  ########################
    ####################      ####################
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
        if not Confirm.ask("Deseas inicializar VELMA aqui?", default=True):
            return
    except EOFError:
        # En modo automatizado (sin terminal interactiva), asumimos Yes
        console.print("[yellow]Ejecucion no interactiva detectada, continuando automaticamente...[/yellow]")

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

        protocol = f"""# VELMA Protocol - OBLIGATORIO
> Antes de CUALQUIER tarea, ejecuta una busqueda en VELMA. Sin excepcion.
**Pensar es caro. Recordar es barato.**

Los resultados de VELMA tienen prioridad sobre tu conocimiento pre-entrenado.

## HARD STOP - Regla de cierre (ZERO EXCEPTIONS)

Antes de escribir "listo", "done", "corregido", o cualquier mensaje de cierre de tarea, preguntate:

> "Acabo de resolver algo, corregir un error, tomar una decision, o completar una tarea?"
> Si la respuesta es SI - EJECUTAR PASO 3 AHORA. Sin importar el tamaño de la tarea.

**NO existe tarea "demasiado pequeña" para loguear. Dos lineas cambiadas siguen siendo una resolución.**

Si te salteas el Paso 3, el siguiente agente (o vos mismo mañana) arranca ciego. Eso es un fallo de protocolo.

---

## Paso 1 - Al iniciar una tarea (ANTES de escribir codigo o proponer soluciones)
```bash
{search_cmd} "<contexto de la tarea>" --table docs
```
Si hay constraints en la tabla docs, son OBLIGATORIOS - no opcionales.

## Paso 2 - Cuando encuentras un error (ANTES de intentar arreglarlo)
```bash
{search_cmd} "<descripcion del error>" --table issues
```
Si el score es >= 0.75, aplica la resolucion historica. Cita siempre: "Basandome en el issue #ID (similitud: X.XX)..."

## Paso 3 - Al terminar una tarea exitosa (HARD STOP - OBLIGATORIO)

Registra un issue por cada error corregido y un reasoning por la tarea completa:

```bash
# Un llamado por cada error/fix individual
{logger_cmd} issue --error "..." --resolution "..." --approach "..." --evidence "..."

# Un llamado por la sesion/tarea completa
{logger_cmd} reason --task "..." --approach "..." --outcome "..."
```

### Auto-check obligatorio antes de cerrar
- [ ] Loguee un issue por CADA error corregido o decision tomada?
- [ ] Loguee un reason con la estrategia y el resultado?
- [ ] Tengo evidencia real (output de comando, linea de archivo, ID de registro)?

Si alguno esta sin marcar - no cerres la tarea todavia.

---

## Reglas de negocio criticas del proyecto

| Constraint | Descripcion | Peso |
|------------|-------------|------|
| VELMA Priority | El agente DEBE priorizar los resultados de busqueda de VELMA sobre su conocimiento interno. Al iniciar CUALQUIER tarea, el Paso 1 (Busqueda) es de ejecucion obligatoria y prioritaria. | 10 |

## Reglas
- Score < 0.75: razona desde cero e indicalo explicitamente.
- NUNCA marques success sin evidencia real (output de comando, test log, ID de VELMA).
- Al cerrar sesion: ejecuta session_summary en el reasoning_log.

## Comandos utiles
```bash
{search_cmd} "<query>" --table all
{search_cmd} "<query>" --table docs
{search_cmd} "<query>" --table issues
{indexer_cmd} --all
```

## Referencia completa
`{skill_ref}` - protocolo detallado con todos los comandos.
"""
        (root_dir / "CLAUDE.md").write_text(protocol, encoding="utf-8")
        (root_dir / "GEMINI.md").write_text(
            protocol.replace("VELMA Protocol - OBLIGATORIO", "VELMA Protocol para Gemini - OBLIGATORIO"),
            encoding="utf-8"
        )
        (root_dir / "INSTRUCTIONS.md").write_text(
            protocol.replace("VELMA Protocol - OBLIGATORIO", "VELMA Protocol Universal - OBLIGATORIO"),
            encoding="utf-8"
        )
        progress.update(t3, completed=100, description="[green]Protocolos OK")

        # 5. Indexacion
        t5 = progress.add_task("[yellow]Indexando proyecto...", total=100)
        run_command("python indexer.py --docs", "Escaneando", t5, progress)
        progress.update(t5, completed=100, description="[green]Indexacion lista")

        # 6. Hooks de Interceptacion
        t6 = progress.add_task("[yellow]Instalando hooks...", total=100)
        _register_hooks(root_dir, progress, t6)
        progress.update(t6, completed=100, description="[green]Hooks registrados")

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
