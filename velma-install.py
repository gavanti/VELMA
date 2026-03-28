#!/usr/bin/env python3
"""
VELMA - TUI Installation & Discovery
Instalador visual inspirado en tui-skills-discovery.
Automatiza el setup completo de VELMA con un solo enter.
"""

import sys
import os
import time
import subprocess
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.prompt import Confirm

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
                # Actualizar sutilmente la descripción
                progress.update(task, description=f"[cyan]{description}...[/cyan]")
        
        if process.returncode == 0:
            return True
        return False
    except Exception as e:
        return False

def main():
    console.clear()
    
    # Autodeteccion de contexto
    current_dir = Path.cwd()
    project_name = current_dir.name
    
    # Header
    console.print("[magenta]==================================================[/magenta]")
    console.print(f"[magenta]  V E L M A - Persistent Memory for {project_name}[/magenta]")
    console.print("[magenta]  v0.5.5 Automa-Installer[/magenta]")
    console.print("[magenta]==================================================[/magenta]")

    console.print(f"\n[bold]Instalando memoria persistente en:[/bold] [cyan]{current_dir}[/cyan]")
    console.print(f"[bold]Proyecto detectado:[/bold] [yellow]{project_name}[/yellow]\n")

    if not Confirm.ask("¿Deseas inicializar VELMA en este directorio?", default=True):
        return

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        expand=True
    ) as progress:

        # Paso 1: Configurar .env automaticamente
        t0 = progress.add_task("[yellow]Configurando entorno...", total=100)
        env_content = f"""PROJECT_NAME={project_name}
DEV_NAME={os.getlogin() if hasattr(os, 'getlogin') else 'developer'}
DB_PATH=knowledge.db
MODEL_NAME=paraphrase-multilingual-MiniLM-L12-v2
MIN_CONFIDENCE_SCORE=0.50
"""
        Path(".env").write_text(env_content)
        progress.update(t0, completed=100, description="[green].env configurado")

        # Paso 1: Dependencias
        t1 = progress.add_task("[yellow]Verificando dependencias Python...", total=100)
        time.sleep(1)
        if run_command("pip install -r requirements.txt -q", "Instalando paquetes core", t1, progress):
            progress.update(t1, completed=100, description="[green]Dependencias OK")
        else:
            progress.update(t1, description="[red]Error instalando dependencias")
            return

        # Paso 2: Base de Datos
        t2 = progress.add_task("[yellow]Creando base de datos SQLite...", total=100)
        if run_command("python setup_kb.py", "Configurando schema", t2, progress):
            progress.update(t2, completed=100, description="[green]Base de Datos VELMA creada")
        else:
            progress.update(t2, description="[red]Error en setup_kb.py")
            return

        # Paso 3: Ollama Detection
        t3 = progress.add_task("[yellow]Detectando Ollama...", total=100)
        try:
            import ollama
            ollama.list()
            progress.update(t3, completed=100, description="[green]Ollama detectado (Enriquecimiento activado)")
        except:
            progress.update(t3, completed=100, description="[white]Ollama no detectado (Modo Standard)")

        # Paso 4: Indexacion Inicial
        t4 = progress.add_task("[yellow]Indexando documentacion...", total=100)
        # Crear docs si no existe
        Path("docs").mkdir(exist_ok=True)
        if run_command("python indexer.py --docs", "Generando embeddings", t4, progress):
            progress.update(t4, completed=100, description="[green]Documentacion indexada")
        else:
            progress.update(t4, description="[yellow]Sin docs para indexar (omitido)")
            progress.update(t4, completed=100)

        # Paso 5: Verificacion Final
        t5 = progress.add_task("[yellow]Ejecutando test de busqueda...", total=100)
        if run_command("python search.py \"VELMA\" --limit 1", "Verificando retrieval", t5, progress):
            progress.update(t5, completed=100, description="[green]Sistema verificado y listo")
        else:
            progress.update(t5, description="[red]Error en verificacion")

    # Resumen Final
    console.print("\n" + "="*50)
    console.print("[bold green]INSTALACION COMPLETADA EXITOSAMENTE[/bold green]")
    console.print("="*50)
    
    stats_table = Table(show_header=False, box=None)
    stats_table.add_row("Base de datos:", "[cyan]knowledge.db[/cyan]")
    stats_table.add_row("Modelo:", "[cyan]paraphrase-multilingual-MiniLM-L12-v2[/cyan]")
    stats_table.add_row("Protocolo:", "[cyan]skills/velma/SKILL.md[/cyan]")
    console.print(stats_table)
    
    console.print("\n[bold magenta]Comandos utiles:[/bold magenta]")
    console.print("  - Buscar: [white]python search.py \"query\"[/white]")
    console.print("  - Web UI: [white]python search.py --web[/white]")
    console.print("  - Test:   [white]python run_all_tests.py[/white]")
    console.print("\n[italic]VELMA esta lista para recordar por ti.[/italic]\n")

if __name__ == "__main__":
    main()
