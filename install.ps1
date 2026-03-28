# VELMA - Smart Bootstrapper for Windows (Enforced Encapsulation)
# Usage: irm https://raw.githubusercontent.com/gavanti/VELMA/main/install.ps1 | iex

$ErrorActionPreference = "Stop"
$REPO_URL = "https://github.com/gavanti/VELMA"
$currentPath = Get-Location
$targetPath = Join-Path $currentPath "VELMA"

function Show-Header {
    Clear-Host
    $ascii = @"
 _        ___    _   ,__ __    ___,  
 (_|   |_// (_)\_|_) /|  |  |  /   |  
   |   |  \__    |    |  |  | |    |  
   |   |  /     _|    |  |  | |    |  
    \_/   \___/(/\___/|  |  |_/\__/\_/ 
"@
    Write-Host $ascii -ForegroundColor Magenta
    Write-Host " --------------------------------------------------" -ForegroundColor Gray
    Write-Host "  VELMA: Persistent Memory for AI Agents" -ForegroundColor White
    Write-Host "  Installing into: ./VELMA/" -ForegroundColor Cyan
    Write-Host " --------------------------------------------------" -ForegroundColor Gray
}

function Start-VelmaInstall {
    Show-Header
    
    # 1. Crear directorio VELMA si no existe
    if (!(Test-Path $targetPath)) {
        Write-Host "[*] Creando carpeta contenedora..." -ForegroundColor Cyan
        New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
    }

    # 2. Descarga y Extraccion Quirurgica
    if (!(Test-Path (Join-Path $targetPath "velma-install.py"))) {
        Write-Host "[?] Descargando nucleo de memoria..." -ForegroundColor Yellow
        
        $zipUrl = "$REPO_URL/archive/refs/heads/main.zip"
        $zipFile = Join-Path $targetPath "v_temp.zip"
        $unpackFolder = Join-Path $targetPath ".v_unpack"

        Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile
        Expand-Archive -Path $zipFile -DestinationPath $unpackFolder -Force
        
        $unpackedInnerDir = Get-ChildItem -Path $unpackFolder | Select-Object -First 1
        
        # MOVER CONTENIDO FORZADO AL DIRECTORIO TARGET
        # Usamos rutas absolutas para evitar que se salgan a la raiz
        Get-ChildItem -Path "$($unpackedInnerDir.FullName)\*" | ForEach-Object {
            $dest = Join-Path $targetPath $_.Name
            Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force
        }
        
        # Limpieza
        Remove-Item $zipFile -Force
        Remove-Item $unpackFolder -Recurse -Force
        Write-Host "[OK] Nucleo instalado exitosamente en ./VELMA" -ForegroundColor Green
    }

    # 3. Lanzar Instalador TUI desde la subcarpeta
    if (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Host "`n[*] Iniciando configuracion bilingue..." -ForegroundColor Magenta
        # Cambiamos directorio solo para la ejecucion de python
        Push-Location $targetPath
        try {
            python -m pip install rich --quiet
            python velma-install.py
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "`n[!] Python no detectado." -ForegroundColor Red
    }
    
    Write-Host "`n[!] RECUERDA: Agrega 'VELMA/' a tu .gitignore para mantener el orden." -ForegroundColor Yellow
}

try { Start-VelmaInstall } catch { Write-Host "`n[!] Error: $($_.Exception.Message)" -ForegroundColor Red }
