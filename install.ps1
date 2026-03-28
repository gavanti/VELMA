# VELMA - Smart Bootstrapper for Windows (Universal Drop-in Version)
# Usage: irm https://raw.githubusercontent.com/gavanti/VELMA/main/install.ps1 | iex

$ErrorActionPreference = "Stop"
$REPO_URL = "https://github.com/gavanti/VELMA"

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
    Write-Host "  Drop-in Installation Protocol" -ForegroundColor White
    Write-Host " --------------------------------------------------" -ForegroundColor Gray
    Write-Host ""
}

function Start-VelmaInstall {
    Show-Header
    
    $currentDir = Get-Location
    Write-Host "[*] Carpeta detectada: $($currentDir.Path)" -ForegroundColor Cyan

    # 1. Descarga Limpia (vía ZIP para evitar colisiones de Git)
    if (!(Test-Path "velma-install.py")) {
        Write-Host "[?] VELMA no detectada. Instalando nucleo bilingue..." -ForegroundColor Yellow
        
        $zipUrl = "$REPO_URL/archive/refs/heads/main.zip"
        $zipFile = "velma_temp.zip"
        $tempFolder = ".velma_unpack"

        Write-Host "[*] Descargando archivos desde GitHub..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile
        
        Write-Host "[*] Desempaquetando componentes..." -ForegroundColor Cyan
        if (Test-Path $tempFolder) { Remove-Item $tempFolder -Recurse -Force }
        Expand-Archive -Path $zipFile -DestinationPath $tempFolder -Force
        
        # Mover contenido de la subcarpeta del ZIP a la raiz actual
        $unpackedDir = Get-ChildItem -Path $tempFolder | Select-Object -First 1
        Copy-Item -Path "$($unpackedDir.FullName)\*" -Destination "." -Recurse -Force
        
        # Limpieza
        Remove-Item $zipFile -Force
        Remove-Item $tempFolder -Recurse -Force
        Write-Host "[OK] Nucleo inyectado correctamente." -ForegroundColor Green
    }

    # 2. Verificar Python
    if (!(Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "`n[!] Python no detectado. Instala Python 3.10+ para continuar." -ForegroundColor Red
        return
    }

    # 3. Lanzar el instalador visual de Python
    Write-Host "`n[*] Iniciando TUI de configuracion..." -ForegroundColor Magenta
    python -m pip install rich --quiet
    python velma-install.py
}

try {
    Start-VelmaInstall
} catch {
    Write-Host "`n[!] Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "    Asegurate de que el repositorio sea PUBLICO en GitHub." -ForegroundColor Gray
}
