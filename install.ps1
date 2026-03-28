# VELMA - Smart Bootstrapper for Windows
# Usage: irm https://raw.githubusercontent.com/gavanti/VELMA/main/install.ps1 | iex

$ErrorActionPreference = "Stop"
$REPO_URL = "https://github.com/gavanti/VELMA"
$currentPath = Get-Location
$targetPath = Join-Path $currentPath "VELMA"

function Show-Header {
    Clear-Host
    $art = @"
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
"@
    Write-Host $art -ForegroundColor Magenta
    Write-Host " -----------------------------------------------------" -ForegroundColor Gray
    Write-Host "  VELMA: Persistent Memory for AI Agents" -ForegroundColor White
    Write-Host " -----------------------------------------------------" -ForegroundColor Gray
    Write-Host ""
}

function Start-VelmaInstall {
    Show-Header
    
    if (!(Test-Path $targetPath)) {
        Write-Host "[*] Preparando carpeta ./VELMA/..." -ForegroundColor Cyan
        New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
    }

    if (!(Test-Path (Join-Path $targetPath "velma-install.py"))) {
        Write-Host "[?] Descargando nucleo..." -ForegroundColor Yellow
        $zipUrl = "$REPO_URL/archive/refs/heads/main.zip"
        $zipFile = Join-Path $targetPath "v.zip"
        $unpack = Join-Path $targetPath ".v_unpack"

        Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile
        Expand-Archive -Path $zipFile -DestinationPath $unpack -Force
        $inner = Get-ChildItem -Path $unpack | Select-Object -First 1
        Copy-Item -Path "$($inner.FullName)\*" -Destination $targetPath -Recurse -Force
        Remove-Item $zipFile, $unpack -Recurse -Force
    }

    if (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Host "[*] Lanzando instalador visual..." -ForegroundColor Magenta
        Push-Location $targetPath
        try {
            python -m pip install rich --quiet
            python velma-install.py
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "[!] Instala Python para continuar." -ForegroundColor Red
    }
}

try { Start-VelmaInstall } catch { Write-Host "`n[!] Error: $($_.Exception.Message)" -ForegroundColor Red }
