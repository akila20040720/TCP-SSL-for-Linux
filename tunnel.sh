#!/bin/bash
# Minimal TLS tunnel launcher
# Usage: ./tunnel.sh <config_file> [--no-monitor]

set -e

# Check for --no-monitor flag
ENABLE_MONITOR=true
if [[ "$2" == "--no-monitor" ]] || [[ "$1" == "--no-monitor" && -n "$2" ]]; then
    ENABLE_MONITOR=false
fi

# Load config
CONFIG_FILE="$1"
if [[ "$1" == "--no-monitor" ]]; then
    CONFIG_FILE="$2"
fi

if [ -z "$CONFIG_FILE" ] || [ ! -f "$CONFIG_FILE" ]; then
    echo "Usage: $0 <config_file> [--no-monitor]"
    echo "Example config:"
    echo "  REMOTE_HOST=aus.hackkcah.xyz"
    echo "  SSH_USER=username"
    echo "  SSH_PASS=password"
    echo "  SSH_PORT=443"
    echo "  TUNNEL_PORT=9090"
    echo "  SOCKS_PORT=2070"
    echo "  SNI=google.lk"
    exit 1
fi

source "$CONFIG_FILE"

# Check expiration
if [ -n "$EXPIRES" ]; then
    EXPIRE_EPOCH=$(date -d "$EXPIRES" +%s 2>/dev/null)
    NOW_EPOCH=$(date +%s)

    if [ $? -ne 0 ]; then
        echo "Error: Invalid expiration date format. Use YYYY-MM-DD"
        exit 1
    fi

    if [ "$NOW_EPOCH" -gt "$EXPIRE_EPOCH" ]; then
        echo "Error: Configuration expired on $EXPIRES"
        notify-send -u critical "Tunnel" "Config expired on $EXPIRES"
        exit 1
    fi

    DAYS_LEFT=$(( ($EXPIRE_EPOCH - $NOW_EPOCH) / 86400 ))
    if [ "$DAYS_LEFT" -le 7 ]; then
        echo "Warning: Config expires in $DAYS_LEFT days ($EXPIRES)"
    fi
fi

# Defaults
SOCKS_PORT=${SOCKS_PORT:-2070}
SNI=${SNI:-google.com}
SSH_PORT=${SSH_PORT:-443}

# Set ports based on monitor mode
if [ "$ENABLE_MONITOR" = true ]; then
    TUNNEL_PORT=${TUNNEL_PORT:-9090}
    INTERNAL_SOCKS_PORT=$((SOCKS_PORT + 10000))  # Use high port internally
    PUBLIC_SOCKS_PORT=$SOCKS_PORT
else
    TUNNEL_PORT=${TUNNEL_PORT:-$SOCKS_PORT}  # Use SOCKS port directly
    INTERNAL_SOCKS_PORT=$SOCKS_PORT
    PUBLIC_SOCKS_PORT=$SOCKS_PORT
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TUNNEL_PY="$SCRIPT_DIR/tunnel.py"
MONITOR_PY="$SCRIPT_DIR/socks_monitor.py"

# Check if ports are available
for p in $TUNNEL_PORT $INTERNAL_SOCKS_PORT $PUBLIC_SOCKS_PORT; do
    sudo lsof -t -i :$p | xargs -r sudo kill
done

# Cleanup function
cleanup() {
    echo "Stopping tunnel..."
    pkill -P $ 2>/dev/null || true
    for p in $TUNNEL_PORT $INTERNAL_SOCKS_PORT $PUBLIC_SOCKS_PORT; do
        sudo lsof -t -i :$p | xargs -r sudo kill
    done
    sleep 1
    exit 0
}

trap cleanup EXIT INT TERM

# Check if tunnel.py exists
if [ ! -f "$TUNNEL_PY" ]; then
    echo "Error: tunnel.py not found at $TUNNEL_PY"
    exit 1
fi

# Start TLS tunnel
echo "[*] Starting TLS tunnel..."
python3 "$TUNNEL_PY" "$REMOTE_HOST" "$TUNNEL_PORT" "$SNI" &
TUNNEL_PID=$!
sleep 2

if ! kill -0 $TUNNEL_PID 2>/dev/null; then
    echo "[!] TLS tunnel failed to start"
    notify-send -u critical "Tunnel Error" "TLS tunnel failed to start"
    exit 1
fi

# Start SSH tunnel
echo "[*] Starting SSH tunnel..."
sshpass -p "$SSH_PASS" ssh \
    -o "ProxyCommand=nc -X CONNECT -x 127.0.0.1:$TUNNEL_PORT %h %p" \
    -o "Compression=no" \
    -o "StrictHostKeyChecking=no" \
    -o "UserKnownHostsFile=/dev/null" \
    -o "ServerAliveInterval=30" \
    -o "ServerAliveCountMax=3" \
    "$SSH_USER@$REMOTE_HOST" -p "$SSH_PORT" -CN -D "$INTERNAL_SOCKS_PORT" &
SSH_PID=$!
sleep 2

if ! kill -0 $SSH_PID 2>/dev/null; then
    echo "[!] SSH tunnel failed"
    notify-send -u critical "Tunnel Error" "SSH connection failed"
    exit 1
fi

# Start SOCKS5 monitor if enabled
if [ "$ENABLE_MONITOR" = true ]; then
    echo "[*] Starting SOCKS5 monitor..."
    if [ ! -f "$MONITOR_PY" ]; then
        echo "[!] Warning: socks_monitor.py not found, monitoring disabled"
    else
        # Add blocklist argument if specified
        MONITOR_ARGS="$PUBLIC_SOCKS_PORT $INTERNAL_SOCKS_PORT"
        if [ -n "$BLOCKLIST" ]; then
            if [ -f "$BLOCKLIST" ]; then
                MONITOR_ARGS="$MONITOR_ARGS $BLOCKLIST"
                echo "[*] Using blocklist: $BLOCKLIST"
            else
                echo "[!] Warning: Blocklist not found: $BLOCKLIST"
            fi
        fi

        python3 "$MONITOR_PY" $MONITOR_ARGS &
        MONITOR_PID=$!
        sleep 1

        if kill -0 $MONITOR_PID 2>/dev/null; then
            echo "[+] SOCKS5 (monitored): 127.0.0.1:$PUBLIC_SOCKS_PORT"
            echo "[+] Status available: ./status.sh"
        else
            echo "[!] Monitor failed to start"
        fi
    fi
fi

echo "[+] Tunnel ready! Press Ctrl+C to stop"
echo ""
echo "========================================="
echo "[+] SERVER = $REMOTE_HOST"
echo "[+] SNI    = $SNI"
echo "[+] SOCKS5 = 127.0.0.1:$([ "$ENABLE_MONITOR" = true ] && echo "$PUBLIC_SOCKS_PORT (shows traffic)" || echo "$PUBLIC_SOCKS_PORT")"
echo "========================================="
echo ""
echo "[+] Tunnel ready! Press Ctrl+C to stop"

# Keep running
wait
