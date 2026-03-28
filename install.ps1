# VELMA - Smart Bootstrapper for Windows (Atomic Version)
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
    Write-Host " --------------------------------------------------" -ForegroundColor Gray
}

function Start-VelmaInstall {
    Show-Header
    $currentDir = Get-Location
    
    # 1. Limpiar rastro de archivos prohibidos (como 'nul') si existen
    if (Test-Path "\\?\$($currentDir.Path)\nul") {
        Write-Host "[!] Detectado rastro de archivo 'nul'. Limpiando..." -ForegroundColor Yellow
        cmd /c "del \\.\$($currentDir.Path)\nul" 2>$null
    }

    # 2. Descarga via ZIP
    if (!(Test-Path "velma-install.py")) {
        Write-Host "[?] Instalando nucleo de memoria..." -ForegroundColor Yellow
        
        $zipUrl = "$REPO_URL/archive/refs/heads/main.zip"
        $zipFile = "v_temp.zip"
        $tempFolder = ".v_unpack"

        Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile
        Expand-Archive -Path $zipFile -DestinationPath $tempFolder -Force
        
        $unpackedDir = Get-ChildItem -Path $tempFolder | Select-Object -First 1
        
        # COPIA POR WHITELIST (Solo lo esencial)
        $whitelist = @("*.py", "*.md", "*.txt", "*.ps1", "templates", "skills", "tests", "requirements.txt")
        
        foreach ($pattern in $whitelist) {
            Get-ChildItem -Path "$($unpackedDir.FullName)\$pattern" | ForEach-Object {
                $dest = Join-Path $currentDir.Path $_.Name
                if ($_.PSIsContainer) {
                    Copy-Item -Path $_.FullName -Destination $dest -Recurse -Force
                } else {
                    Copy-Item -Path $_.FullName -Destination $dest -Force
                }
            }
        }
        
        # Limpieza
        Remove-Item $zipFile -Force
        Remove-Item $tempFolder -Recurse -Force
        Write-Host "[OK] Nucleo inyectado." -ForegroundColor Green
    }

    # 3. Lanzar TUI
    if (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Host "`n[*] Iniciando configuracion..." -ForegroundColor Magenta
        python -m pip install rich --quiet
        python velma-install.py
    } else {
        Write-Host "`n[!] Python no encontrado." -ForegroundColor Red
    }
}

try { Start-VelmaInstall } catch { Write-Host "`n[!] Error: $($_.Exception.Message)" -ForegroundColor Red }
