#!/bin/bash
# Get tunnel status
# Usage: ./status.sh [--watch] [format]
# Format options: full (default), speed, bytes, connections, uptime
# Or custom format string with variables: {up_kbps}, {down_kbps}, {bytes_up}, {bytes_down}, {uptime}, {connections}, {active}

SOCKET_PATH="/tmp/socks_monitor.sock"

get_status() {
    local format="${1:-full}"

    if [ ! -S "$SOCKET_PATH" ]; then
        echo "Not running"

        # Debug info
        if ps aux | grep -q "[s]ocks_monitor.py"; then
            echo "Note: socks_monitor.py is running but socket not created"
            echo "Check for errors in the monitor process"
        fi
        return 1
    fi

    # Query status using Python
    python3 << EOF
import socket
import json
import sys
import os

try:
    # Create a temporary socket for the client
    client_socket_path = f"/tmp/socks_status_client_{os.getpid()}.sock"

    # Clean up if exists
    if os.path.exists(client_socket_path):
        os.remove(client_socket_path)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(client_socket_path)
    sock.settimeout(2)

    # Send request
    sock.sendto(b'status', '/tmp/socks_monitor.sock')

    # Receive response
    data, _ = sock.recvfrom(4096)
    sock.close()

    # Clean up client socket
    os.remove(client_socket_path)

    stats = json.loads(data.decode())

    uptime = stats['uptime']
    hours = uptime // 3600
    mins = (uptime % 3600) // 60
    secs = uptime % 60

    up_mb = stats['bytes_up'] / 1024 / 1024
    down_mb = stats['bytes_down'] / 1024 / 1024

    format_str = "$format"

    if format_str == "full":
        print(f"Uptime: {hours:02d}:{mins:02d}:{secs:02d}")
        print(f"Upload: {up_mb:.2f} MB ({stats['up_kbps']:.1f} kbps avg)")
        print(f"Download: {down_mb:.2f} MB ({stats['down_kbps']:.1f} kbps avg)")
        print(f"Connections: {stats['connections']} total, {stats['active']} active")
        if stats.get('blocked', 0) > 0:
            print(f"Blocked: {stats['blocked']} requests")
    elif format_str == "speed":
        print(f"{stats['up_kbps']:.1f} kbps ↑ | {stats['down_kbps']:.1f} kbps ↓")
    elif format_str == "bytes":
        print(f"{up_mb:.2f} MB ↑ | {down_mb:.2f} MB ↓")
    elif format_str == "connections":
        print(f"{stats['connections']} total | {stats['active']} active")
    elif format_str == "uptime":
        print(f"{hours:02d}:{mins:02d}:{secs:02d}")
    else:
        # Custom format string
        output = format_str
        output = output.replace("{up_kbps}", f"{stats['up_kbps']:.1f}")
        output = output.replace("{down_kbps}", f"{stats['down_kbps']:.1f}")
        output = output.replace("{bytes_up}", f"{up_mb:.2f}")
        output = output.replace("{bytes_down}", f"{down_mb:.2f}")
        output = output.replace("{uptime}", f"{hours:02d}:{mins:02d}:{secs:02d}")
        output = output.replace("{connections}", str(stats['connections']))
        output = output.replace("{active}", str(stats['active']))
        print(output)

except Exception as e:
    if "Connection refused" in str(e) or "No such file" in str(e):
        print("Disconnected")
    else:
        print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
EOF
}

if [ "$1" = "--watch" ] || [ "$1" = "-w" ]; then
    FORMAT="${2:-full}"
    watch -n 1 "$0" "$FORMAT"
else
    get_status "$1"
fi
