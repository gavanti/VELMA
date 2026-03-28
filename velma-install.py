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

    if not Confirm.ask("¿Deseas inicializar VELMA aquí?", default=True):
        return

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

        # 4. Protocolos (en la raiz)
        t3 = progress.add_task("[yellow]Instalando protocolos...", total=100)
        claude_content = f"# VELMA Protocol\n> **SKILL**: `{cmd_prefix}skills/velma/SKILL.md`\n\n## Search\npython {cmd_prefix}search.py \"query\"\n"
        (root_dir / "CLAUDE.md").write_text(claude_content)
        (root_dir / "GEMINI.md").write_text(claude_content.replace("CLAUDE", "GEMINI"))
        (root_dir / "INSTRUCTIONS.md").write_text(f"VELMA Memory System installed in ./{cmd_prefix}")
        progress.update(t3, completed=100, description="[green]Protocolos OK")

        # 5. Indexacion
        t4 = progress.add_task("[yellow]Indexando proyecto...", total=100)
        run_command("python indexer.py --docs", "Escaneando", t4, progress)
        progress.update(t4, completed=100, description="[green]Indexacion lista")

    console.print(f"\n[bold green]INSTALACION COMPLETADA EN ./{cmd_prefix}[/bold green]")
    console.print(f"Uso: [white]python {cmd_prefix}search.py \"tu query\"[/white]\n")

if __name__ == "__main__":
    main()
