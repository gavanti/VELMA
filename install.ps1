# VELMA - Smart Bootstrapper for Windows
# Usage: irm https://raw.githubusercontent.com/TU_USUARIO/VELMA/main/install.ps1 | iex

$ErrorActionPreference = "Stop"
$REPO_URL = "https://github.com/gavanti/VELMA.git"

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
    Write-Host "  Standardized Agent Skill & Knowledge Base" -ForegroundColor White
    Write-Host " --------------------------------------------------" -ForegroundColor Gray
    Write-Host ""
}

function Start-VelmaInstall {
    Show-Header
    
    $currentDir = Get-Location
    Write-Host "[*] Preparando instalacion en: $($currentDir.Path)" -ForegroundColor Cyan
    Write-Host ""

    # 1. Verificar si el repo ya existe aquí, si no, descargarlo
    if (!(Test-Path "velma-install.py")) {
        Write-Host "[?] VELMA no detectada. ¿Deseas descargar el núcleo del sistema?" -ForegroundColor Yellow
        $choice = Read-Host "[y/n] (y)"
        if ($choice -eq "n") { Write-Host "Abortado."; return }

        Write-Host "[*] Descargando VELMA desde el repositorio..." -ForegroundColor Cyan
        if (Get-Command git -ErrorAction SilentlyContinue) {
            # Clonar si hay Git
            git clone --depth 1 $REPO_URL .temp_velma
            Move-Item .temp_velma/* . -Force
            Remove-Item .temp_velma -Recurse -Force
        } else {
            # Descarga por ZIP si no hay Git (más universal)
            Write-Host "[*] Git no detectado, descargando via WebRequest..." -ForegroundColor Yellow
            $zipUrl = "$($REPO_URL.Replace('.git',''))/archive/refs/heads/main.zip"
            Invoke-WebRequest -Uri $zipUrl -OutFile "velma.zip"
            Expand-Archive -Path "velma.zip" -DestinationPath ".temp_zip" -Force
            $innerDir = Get-ChildItem ".temp_zip" | Select-Object -First 1
            Move-Item "$($innerDir.FullName)\*" . -Force
            Remove-Item "velma.zip", ".temp_zip" -Recurse -Force
        }
    }

    # 2. Verificar Python
    if (!(Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "`n[!] Python no detectado. Instala Python 3.10+ para continuar." -ForegroundColor Red
        Write-Host "    Link: https://www.python.org/downloads/"
        return
    }

    # 3. Lanzar el instalador visual de Python
    Write-Host "`n[*] Iniciando interfaz visual de instalacion..." -ForegroundColor Magenta
    python -m pip install rich --quiet
    python velma-install.py
}

try {
    Start-VelmaInstall
} catch {
    Write-Host "`n[!] Error: $($_.Exception.Message)" -ForegroundColor Red
}
