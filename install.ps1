# VELMA - Smart Bootstrapper & Updater for Windows (v0.9.0)
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
}

function Start-VelmaInstall {
    Show-Header
    
    $localVersionFile = Join-Path $targetPath "version.txt"
    $isUpdate = Test-Path $localVersionFile
    
    if ($isUpdate) {
        $localVersion = Get-Content $localVersionFile
        Write-Host "[*] Detectada instalacion existente (Version: $localVersion)" -ForegroundColor Cyan
        
        # Consultar version remota (simplificado por ahora, asumimos que siempre quiere el ultimo main)
        Write-Host "[?] ¿Deseas buscar actualizaciones y refrescar el codigo?" -ForegroundColor Yellow
        $choice = Read-Host "[y/n] (y)"
        if ($choice -eq "n") { 
            Write-Host "[*] Saltando actualizacion de archivos." -ForegroundColor Gray
        } else {
            Update-Files
        }
    } else {
        Write-Host "[*] Iniciando instalacion limpia en ./VELMA/..." -ForegroundColor Cyan
        New-Item -ItemType Directory -Path $targetPath -Force | Out-Null
        Update-Files
    }

    # Lanzar instalador de Python (siempre, para asegurar DB y dependencias)
    if (Get-Command python -ErrorAction SilentlyContinue) {
        Write-Host "`n[*] Verificando integridad del sistema..." -ForegroundColor Magenta
        Push-Location $targetPath
        try {
            python -m pip install rich --quiet
            python velma-install.py
        } finally {
            Pop-Location
        }
    }
}

function Update-Files {
    Write-Host "[*] Descargando ultimas mejoras desde GitHub..." -ForegroundColor Cyan
    
    $zipUrl = "$REPO_URL/archive/refs/heads/main.zip"
    $zipFile = Join-Path $targetPath "v_update.zip"
    $unpack = Join-Path $targetPath ".v_unpack"

    Invoke-WebRequest -Uri $zipUrl -OutFile $zipFile
    Expand-Archive -Path $zipFile -DestinationPath $unpack -Force
    $inner = Get-ChildItem -Path $unpack | Select-Object -First 1
    
    # MOVER SOLO CODIGO, PRESERVAR DATA
    # Excluimos explícitamente knowledge.db y .env si ya existen
    Get-ChildItem -Path "$($inner.FullName)\*" -Recurse | ForEach-Object {
        $dest = $_.FullName.Replace($inner.FullName, $targetPath)
        
        # REGLA DE ORO: NO SOBRESCRIBIR MEMORIA NI CONFIG
        if ($_.Name -eq "knowledge.db" -and (Test-Path $dest)) { return }
        if ($_.Name -eq ".env" -and (Test-Path $dest)) { return }
        
        if ($_.PSIsContainer) {
            if (!(Test-Path $dest)) { New-Item -ItemType Directory -Path $dest -ItemType Directory -Force | Out-Null }
        } else {
            # Asegurar que el directorio de destino existe antes de copiar el archivo
            $destDir = Split-Path $dest
            if (!(Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
            Copy-Item -Path $_.FullName -Destination $dest -Force
        }
    }
    
    Remove-Item $zipFile -Force
    Remove-Item $unpack -Recurse -Force
    Write-Host "[OK] Archivos actualizados exitosamente." -ForegroundColor Green
}

try { Start-VelmaInstall } catch { Write-Host "`n[!] Error: $($_.Exception.Message)" -ForegroundColor Red }
