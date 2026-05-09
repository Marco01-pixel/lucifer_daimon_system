cat > ~/start_sistema.sh << 'EOF'
#!/data/data/com.termux/files/usr/bin/env bash

# ==============================================================================
# UBER DAEMON SUPERVISOR v3
# Termux + Ollama + Cloudflare + Python IA
# ==============================================================================

# ==============================================================================
# CONFIGURACION
# ==============================================================================

LOG_DIR="$HOME/.daemon_logs"
LOG_FILE="$LOG_DIR/supervisor.log"

PID_DIR="$HOME/.daemon_pids"
PID_FILE="$PID_DIR/supervisor.pid"

HEARTBEAT_DIR="$HOME/.daemon_heartbeats"

APP_DIR="$HOME/lucifer_prometeo"
APP_FILE="00_start_all.py"

CHECK_INTERVAL=10
MAX_LOG_SIZE=5242880

# ==============================================================================
# PREPARAR DIRECTORIOS
# ==============================================================================

mkdir -p "$LOG_DIR"
mkdir -p "$PID_DIR"
mkdir -p "$HEARTBEAT_DIR"

# ==============================================================================
# LOGGING
# ==============================================================================

log() {
    local ts
    ts=$(date '+%Y-%m-%d %H:%M:%S')

    echo "[$ts] $*" | tee -a "$LOG_FILE"
}

# ==============================================================================
# ROTAR LOGS
# ==============================================================================

rotate_logs() {

    if [ -f "$LOG_FILE" ]; then

        size=$(stat -c%s "$LOG_FILE" 2>/dev/null || echo 0)

        if [ "$size" -gt "$MAX_LOG_SIZE" ]; then

            mv "$LOG_FILE" "$LOG_FILE.old"

            touch "$LOG_FILE"

            log "Logs rotados"
        fi
    fi
}

# ==============================================================================
# WAKELOCK
# ==============================================================================

acquire_wakelock() {

    command -v termux-wake-lock >/dev/null 2>&1 && {
        termux-wake-lock 2>/dev/null || true
    }
}

release_wakelock() {

    command -v termux-wake-unlock >/dev/null 2>&1 && {
        termux-wake-unlock 2>/dev/null || true
    }
}

# ==============================================================================
# HEARTBEAT
# ==============================================================================

heartbeat() {
    touch "$HEARTBEAT_DIR/$1.beat"
}

# ==============================================================================
# CHECK PORT
# ==============================================================================

check_port() {

    local port=$1

    bash -c "exec 3<>/dev/tcp/127.0.0.1/$port" 2>/dev/null && {
        exec 3>&-
        return 0
    }

    return 1
}

# ==============================================================================
# TMUX SERVICE
# ==============================================================================

start_tmux_service() {

    local name="$1"
    local cmd="$2"

    tmux has-session -t "$name" 2>/dev/null && {
        tmux kill-session -t "$name" 2>/dev/null
    }

    tmux new-session -d -s "$name" "$cmd"

    sleep 3

    if tmux has-session -t "$name" 2>/dev/null; then

        log "[OK] $name iniciado"

        heartbeat "$name"

        return 0
    fi

    log "[FALLO] $name no inicio"

    return 1
}

# ==============================================================================
# OLLAMA
# ==============================================================================

ensure_ollama() {

    if ! check_port 11434; then

        log "Ollama caido"

        start_tmux_service \
            "ollama" \
            "ollama serve"

        sleep 8
    fi

    check_port 11434 && heartbeat "ollama"
}

# ==============================================================================
# APP IA
# ==============================================================================

ensure_app() {

    if ! check_port 8989; then

        log "App IA caida"

        start_tmux_service \
            "app" \
            "cd $APP_DIR && python $APP_FILE"

        sleep 5
    fi

    check_port 8989 && heartbeat "app"
}

# ==============================================================================
# TUNNEL APP
# ==============================================================================

ensure_tunnel_app() {

    if ! tmux has-session -t "tunnel_app" 2>/dev/null; then

        log "Tunnel APP caido"

        start_tmux_service \
            "tunnel_app" \
            "while true; do cloudflared tunnel --no-autoupdate run uber_tunel 2>&1; sleep 5; done"
    fi

    heartbeat "tunnel_app"
}

# ==============================================================================
# TUNNEL OLLAMA
# ==============================================================================

ensure_tunnel_ollama() {

    if ! tmux has-session -t "tunnel_ollama" 2>/dev/null; then

        log "Tunnel Ollama caido"

        start_tmux_service \
            "tunnel_ollama" \
            "while true; do cloudflared tunnel --no-autoupdate --url http://localhost:11434 2>&1; sleep 5; done"
    fi

    heartbeat "tunnel_ollama"
}

# ==============================================================================
# LIMPIEZA
# ==============================================================================

cleanup() {

    log "Deteniendo sistema"

    rm -f "$PID_FILE"

    tmux kill-server 2>/dev/null || true

    pkill -f "ollama serve" 2>/dev/null || true
    pkill -f "$APP_FILE" 2>/dev/null || true
    pkill -f "cloudflared" 2>/dev/null || true

    release_wakelock

    command -v termux-notification-remove >/dev/null 2>&1 && {
        termux-notification-remove 777 2>/dev/null || true
    }

    log "Sistema detenido"
}

# ==============================================================================
# STATUS
# ==============================================================================

show_status() {

    echo ""
    echo "==============================="
    echo " UBER DAEMON STATUS"
    echo "==============================="
    echo ""

    echo "--- TMUX ---"

    tmux ls 2>/dev/null || echo "Sin sesiones"

    echo ""
    echo "--- PUERTOS ---"

    check_port 11434 \
        && echo "OLLAMA : OK" \
        || echo "OLLAMA : OFF"

    check_port 8989 \
        && echo "APP     : OK" \
        || echo "APP     : OFF"

    echo ""
    echo "--- PROCESOS ---"

    pgrep -af "ollama|cloudflared|00_start_all|start_sistema" \
        || echo "Nada ejecutandose"

    echo ""
}

# ==============================================================================
# EDITOR
# ==============================================================================

edit_mode() {

    cleanup

    echo ""
    echo "Abriendo editor..."
    echo ""

    cd "$APP_DIR" && nano "$APP_FILE"

    echo ""
    echo "Para reiniciar:"
    echo "bash ~/start_sistema.sh start"
}

# ==============================================================================
# LOOP PRINCIPAL
# ==============================================================================

main_loop() {

    echo $$ > "$PID_FILE"

    acquire_wakelock

    # Notificacion persistente
    command -v termux-notification >/dev/null 2>&1 && {

        termux-notification \
            --id 777 \
            --ongoing \
            --title "Daemon activo" \
            --content "Supervisor corriendo" \
            --priority high
    }

    log "===================================="
    log "UBER DAEMON INICIADO"
    log "PID: $$"
    log "===================================="

    cycle=0

    while true; do

        cycle=$((cycle + 1))

        rotate_logs

        acquire_wakelock

        ensure_ollama

        ensure_app

        ensure_tunnel_app

        ensure_tunnel_ollama

        if [ $((cycle % 6)) -eq 0 ]; then
            log "Heartbeat general OK"
        fi

        sleep "$CHECK_INTERVAL"
    done
}

# ==============================================================================
# ENTRYPOINT
# ==============================================================================

case "${1:-start}" in

    start|iniciar)

        if [ -f "$PID_FILE" ]; then

            old_pid=$(cat "$PID_FILE" 2>/dev/null || echo "")

            if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then

                echo "Supervisor ya activo"
                echo "PID: $old_pid"

                exit 0
            fi
        fi

        main_loop
        ;;

    stop|detener)

        if [ -f "$PID_FILE" ]; then

            pid=$(cat "$PID_FILE")

            kill -TERM "$pid" 2>/dev/null || true

            sleep 2

            kill -KILL "$pid" 2>/dev/null || true
        fi

        cleanup
        ;;

    restart|reiniciar)

        bash "$0" stop

        sleep 3

        bash "$0" start
        ;;

    status|estado)

        show_status
        ;;

    log|logs)

        tail -f "$LOG_FILE"
        ;;

    edit|editar)

        edit_mode
        ;;

    *)

        echo ""
        echo "=================================="
        echo " UBER DAEMON CONTROL"
        echo "=================================="
        echo ""
        echo " start     - iniciar supervisor"
        echo " stop      - detener todo"
        echo " restart   - reiniciar"
        echo " status    - estado general"
        echo " log       - logs en vivo"
        echo " edit      - editar app"
        echo ""
        ;;
esac
EOF
