# VELMA PowerShell Hooks
# Intercepta comandos de agentes para inyectar contexto persistente automaticamente.

function _velma_get_root {
    git rev-parse --show-toplevel 2>$null
}

function _velma_intercept {
    param($agent_cmd, $args_list)
    
    $args_string = ""
    if ($args_list) { $args_string = $args_list -join " " }
    
    if ($args_string -like "*--no-velma*") {
        $clean_args = $args_string -replace "--no-velma", ""
        $original_cmd = Get-Command $agent_cmd -CommandType Application, ExternalScript | Select-Object -First 1 -ExpandProperty Definition
        & $original_cmd $clean_args
        return
    }

    $root = _velma_get_root
    if ($root -and (Test-Path "$root/search.py")) {
        # Ejecutar busqueda silenciosa
        $context = python "$root/search.py" "$args_string" --format context 2>$null
        $env:VELMA_CONTEXT = $context -join "`n"
        
        # Notificar al usuario (stderr)
        [Console]::Error.WriteLine("[VELMA] Contexto inyectado para $agent_cmd")
    }

    $original_cmd = Get-Command $agent_cmd -CommandType Application, ExternalScript | Select-Object -First 1 -ExpandProperty Definition
    & $original_cmd @args_list
}

function claude { _velma_intercept "claude" $args }
function gemini { _velma_intercept "gemini" $args }
function opencode { _velma_intercept "opencode" $args }
