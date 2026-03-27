#!/usr/bin/env python3
"""
SOCKS5 monitoring proxy
Usage: python socks_monitor.py [listen_port] [upstream_port] [blocklist_file]
"""

import socket
import select
import struct
import sys
import threading
import time
import json
import os

# Global stats
stats = {
    "bytes_up": 0,
    "bytes_down": 0,
    "start_time": time.time(),
    "connections": 0,
    "active": 0,
    "last_check": time.time(),
    "last_bytes_up": 0,
    "last_bytes_down": 0,
    "blocked": 0
}
stats_lock = threading.Lock()

SOCKET_PATH = "/tmp/socks_monitor.sock"

# Blocklist
blocked_domains = set()

def load_blocklist(filepath):
    """Load domains from blocklist file"""
    if not filepath or not os.path.exists(filepath):
        return

    count = 0
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                # Handle format: 0.0.0.0 domain.com or just domain.com
                parts = line.split()
                domain = parts[-1] if parts else None
                if domain:
                    blocked_domains.add(domain.lower())
                    count += 1

    print(f"[*] Loaded {count} blocked domains")


def get_target(data):
    """Parse SOCKS5 target from request"""
    try:
        if len(data) < 5 or data[3] != 0x03:  # Only handle domain names
            return None
        domain_len = data[4]
        if len(data) < 7 + domain_len:
            return None
        domain = data[5:5+domain_len].decode('utf-8', errors='ignore')
        port = struct.unpack('!H', data[5+domain_len:7+domain_len])[0]
        return f"{domain}:{port}"
    except:
        return None

def tunnel(c, u):
    """Bidirectional forwarding"""
    s = [c, u]
    up = down = 0
    while True:
        try:
            r, _, _ = select.select(s, [], [], 60)
            if not r:
                continue
            for sock in r:
                data = sock.recv(32768)
                if not data:
                    return up, down
                if sock is c:
                    u.sendall(data)
                    up += len(data)
                else:
                    c.sendall(data)
                    down += len(data)
        except:
            return up, down

def handle(client, up_port):
    """Handle SOCKS5 connection"""
    up = None
    try:
        with stats_lock:
            stats["connections"] += 1
            stats["active"] += 1

        # Receive client greeting
        greeting = client.recv(256)
        if len(greeting) < 2 or greeting[0] != 0x05:
            return

        # Send no-auth response to client
        client.sendall(b'\x05\x00')

        # Get connection request from client
        req = client.recv(4096)
        if len(req) < 4:
            return

        target = get_target(req) or "unknown"
        target_domain = target.split(':')[0].lower()

        # Check if domain is blocked
        if target_domain in blocked_domains:
            print(f"[✗] {target} - blocked")
            # Send connection refused response
            client.sendall(b'\x05\x05\x00\x01\x00\x00\x00\x00\x00\x00')
            with stats_lock:
                stats["blocked"] += 1
                stats["active"] -= 1
            return

        print(f"[+] → {target}")

        # Connect to upstream SOCKS5
        up = socket.socket()
        up.connect(('127.0.0.1', up_port))

        # Do proper SOCKS5 handshake with upstream
        up.sendall(greeting)  # Forward original greeting
        up_greeting_resp = up.recv(256)  # Get upstream response

        # Forward client's connection request to upstream
        up.sendall(req)
        resp = up.recv(256)

        # Forward upstream response to client
        client.sendall(resp)

        # Check if connection succeeded
        if len(resp) < 2 or resp[1] != 0x00:
            print(f"[!] {target} - connection failed")
            return

        # Tunnel data
        up_bytes, down_bytes = tunnel(client, up)

        with stats_lock:
            stats["bytes_up"] += up_bytes
            stats["bytes_down"] += down_bytes
            stats["active"] -= 1

        total = up_bytes + down_bytes
        size = f"{total/1024/1024:.1f}MB" if total > 1048576 else f"{total/1024:.1f}KB" if total > 1024 else f"{total}B"
        print(f"[✓] {target} - {size}")
    except Exception as e:
        print(f"[!] Handler error: {e}")
        with stats_lock:
            stats["active"] -= 1
    finally:
        try:
            client.close()
        except:
            pass
        try:
            if up:
                up.close()
        except:
            pass

def status_server():
    """Unix socket server for status queries"""
    try:
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        sock.bind(SOCKET_PATH)
        os.chmod(SOCKET_PATH, 0o666)

        print(f"[*] Status socket: {SOCKET_PATH}")

        while True:
            try:
                # For datagram sockets, we need to handle empty messages differently
                sock.settimeout(None)
                data, addr = sock.recvfrom(1024)

                elapsed = time.time() - stats["start_time"]

                with stats_lock:
                    response = {
                        "uptime": int(elapsed),
                        "bytes_up": stats["bytes_up"],
                        "bytes_down": stats["bytes_down"],
                        "up_kbps": (stats["bytes_up"] * 8) / 1000 / max(1, elapsed),
                        "down_kbps": (stats["bytes_down"] * 8) / 1000 / max(1, elapsed),
                        "connections": stats["connections"],
                        "active": stats["active"]
                    }

                # Send response back
                if addr:
                    sock.sendto(json.dumps(response).encode(), addr)
            except Exception as e:
                print(f"[!] Status error: {e}")
                continue
    except Exception as e:
        print(f"[!] Failed to create status socket: {e}")
        import traceback
        traceback.print_exc()

def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 2080
    up_port = int(sys.argv[2]) if len(sys.argv) > 2 else 2070
    blocklist = sys.argv[3] if len(sys.argv) > 3 else None

    # Load blocklist
    if blocklist:
        load_blocklist(blocklist)

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(('127.0.0.1', port))
    s.listen(5)

    # Start status server
    threading.Thread(target=status_server, daemon=True).start()

    print(f"[*] Monitoring 127.0.0.1:{port} → 127.0.0.1:{up_port}")

    try:
        while True:
            c, _ = s.accept()
            threading.Thread(target=handle, args=(c, up_port), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[*] Bye")
    finally:
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)

if __name__ == "__main__":
    main()
