# VELMA - One-Click Bootstrapper for Windows
# Usage: irm https://raw.githubusercontent.com/your-repo/velma/main/install.ps1 | iex

$ErrorActionPreference = "Stop"

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
    
    Write-Host "[*] Bienvenido a VELMA." -ForegroundColor Cyan
    Write-Host "    VELMA permite a tus agentes recordar soluciones pasadas y"
    Write-Host "    reglas de negocio sin gastar tokens en razonamiento repetitivo."
    Write-Host ""
    Write-Host "[?] Este script realizara las siguientes acciones:" -ForegroundColor Yellow
    Write-Host "    1. Clonar/Verificar archivos de VELMA"
    Write-Host "    2. Configurar entorno Python y dependencias"
    Write-Host "    3. Inicializar Base de Datos Vectorial"
    Write-Host "    4. Activar Protocolo de Skills"
    Write-Host ""

    $confirm = Read-Host "Presiona ENTER para comenzar la instalacion (o Ctrl+C para cancelar)"
    
    # 1. Verificar Python
    Write-Host "`n[*] Verificando entorno..." -ForegroundColor Cyan
    if (!(Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Host "[!] Python no detectado. Por favor instala Python 3.10+ para continuar." -ForegroundColor Red
        return
    }

    # 2. Instalar Rich para la TUI de Python si no esta
    Write-Host "[*] Preparando interfaz visual..." -ForegroundColor Cyan
    python -m pip install rich --quiet

    # 3. Lanzar el instalador principal de VELMA
    if (Test-Path "velma-install.py") {
        python velma-install.py
    } else {
        Write-Host "[!] No se encontro velma-install.py en el directorio actual." -ForegroundColor Red
        Write-Host "    Asegurate de ejecutar este script en la raiz del repo."
    }
}

try {
    Start-VelmaInstall
} catch {
    Write-Host "`n[!] Error inesperado: $($_.Exception.Message)" -ForegroundColor Red
}
