# VELMA - Smart Bootstrapper for Windows (Encapsulated Version)
# Usage: irm https://raw.githubusercontent.com/gavanti/VELMA/main/install.ps1 | iex

$ErrorActionPreference = "Stop"
$REPO_URL = "https://github.com/gavanti/VELMA"
$TARGET_DIR = "VELMA"

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
    Write-Host "  Encapsulated Installation" -ForegroundColor White
    Write-Host " --------------------------------------------------" -ForegroundColor Gray
}

function Start-VelmaInstall {
    Show-Header
    
    # 1. Crear directorio encapsulado
    if (!(Test-Path $TARGET_DIR)) {
        New-Item -ItemType Directory -Path $TARGET_DIR | Out-Null
    }
    
    Set-Location $TARGET_DIR

    # 2. Descarga via ZIP dentro de la carpeta VELMA
    if (!(Test-Path "velma-install.py")) {
        Write-Host "[?] Instalando nucleo de memoria en /$TARGET_DIR..." -ForegroundColor Yellow
        
        $zipUrl = "$REPO_URL/archive/refs/heads/main.zip"
        $zipFile = "v_temp.zip"
        $tempFolder = ".v_unpack"

        Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile
        Expand-Archive -Path $zipFile -DestinationPath $tempFolder -Force
        
        $unpackedDir = Get-ChildItem -Path $tempFolder | Select-Object -First 1
        
        # Mover TODO el contenido del ZIP a la subcarpeta VELMA/
        Copy-Item -Path "$($unpackedDir.FullName)\*" -Destination "." -Recurse -Force
        
        # Limpieza de archivos temporales
        Remove-Item $zipFile -Force
        Remove-Item $tempFolder -Recurse -Force
        Write-Host "[OK] Nucleo instalado en ./$TARGET_DIR" -ForegroundColor Green
    }

    # 3. Lanzar Instalador TUI
    if (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Host "`n[*] Iniciando configuracion..." -ForegroundColor Magenta
        python -m pip install rich --quiet
        python velma-install.py
    } else {
        Write-Host "`n[!] Python no encontrado." -ForegroundColor Red
    }
    
    # Volver a la carpeta raiz del proyecto
    Set-Location ..
    Write-Host "`n[CONSEJO] Agrega '$TARGET_DIR/' a tu .gitignore para mantener tu repo limpio." -ForegroundColor Gray
}

try { Start-VelmaInstall } catch { Write-Host "`n[!] Error: $($_.Exception.Message)" -ForegroundColor Red }
