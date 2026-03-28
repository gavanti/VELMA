# VELMA - Smart Bootstrapper for Windows (Ultra-Safe Version)
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

    # 1. Limpieza de residuos de intentos fallidos
    if (Test-Path ".velma_unpack") { Remove-Item ".velma_unpack" -Recurse -Force -ErrorAction SilentlyContinue }
    if (Test-Path "velma_temp.zip") { Remove-Item "velma_temp.zip" -Force -ErrorAction SilentlyContinue }

    # 2. Descarga Limpia via ZIP
    if (!(Test-Path "velma-install.py")) {
        Write-Host "[?] VELMA no detectada. Instalando nucleo..." -ForegroundColor Yellow
        
        $zipUrl = "$REPO_URL/archive/refs/heads/main.zip"
        $zipFile = "velma_temp.zip"
        $tempFolder = ".velma_unpack"

        Write-Host "[*] Descargando desde GitHub..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile
        
        Write-Host "[*] Desempaquetando..." -ForegroundColor Cyan
        Expand-Archive -Path $zipFile -DestinationPath $tempFolder -Force
        
        $unpackedDir = Get-ChildItem -Path $tempFolder | Select-Object -First 1
        
        # MOVER ARCHIVOS UNO POR UNO (Surgical Move)
        # Saltamos .git, .github y el archivo prohibido 'nul'
        Get-ChildItem -Path "$($unpackedDir.FullName)\*" -Recurse | ForEach-Object {
            $destPath = $_.FullName.Replace($unpackedDir.FullName, $currentDir.Path)
            $destDir = Split-Path $destPath
            
            # Filtros de seguridad
            if ($_.Name -eq "nul") { return } # Saltar el archivo prohibido de Windows
            if ($_.FullName -like "*\.git\*") { return } # Saltar cualquier rastro de git
            if ($_.FullName -like "*\.github\*") { return } # Saltar workflows
            
            if ($_.PSIsContainer) {
                if (!(Test-Path $destPath)) { New-Item -ItemType Directory -Path $destPath -Force | Out-Null }
            } else {
                if (!(Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
                Copy-Item -Path $_.FullName -Destination $destPath -Force
            }
        }
        
        # Limpieza final
        Remove-Item $zipFile -Force
        Remove-Item $tempFolder -Recurse -Force
        Write-Host "[OK] Nucleo inyectado sin conflictos." -ForegroundColor Green
    }

    # 3. Verificar Python
    if (!(Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "`n[!] Python no detectado. Instala Python 3.10+." -ForegroundColor Red
        return
    }

    # 4. Lanzar el instalador visual
    Write-Host "`n[*] Iniciando configuracion..." -ForegroundColor Magenta
    python -m pip install rich --quiet
    python velma-install.py
}

try {
    Start-VelmaInstall
} catch {
    Write-Host "`n[!] Error: $($_.Exception.Message)" -ForegroundColor Red
}
