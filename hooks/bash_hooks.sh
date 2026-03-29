# VELMA Bash Hooks
# Intercepta comandos de agentes para inyectar contexto persistente automaticamente.

function _velma_get_root() {
    git rev-parse --show-toplevel 2>/dev/null
}

function _velma_intercept() {
    local agent_cmd=$1
    shift
    local args="$@"
    
    if [[ "$args" == *"--no-velma"* ]]; then
        command $agent_cmd ${args/--no-velma/}
        return
    fi

    local root=$(_velma_get_root)
    if [ -f "$root/search.py" ]; then
        # Ejecutar busqueda silenciosa
        local context=$(python "$root/search.py" "$args" --format context 2>/dev/null)
        export VELMA_CONTEXT="$context"
        
        # Notificar al usuario (stderr)
        echo "[VELMA] Contexto inyectado para $agent_cmd" >&2
    fi

    command $agent_cmd "$@"
}

# Hooks para agentes conocidos
function claude() { _velma_intercept "claude" "$@"; }
function gemini() { _velma_intercept "gemini" "$@"; }
function opencode() { _velma_intercept "opencode" "$@"; }
