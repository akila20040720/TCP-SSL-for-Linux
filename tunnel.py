#!/usr/bin/env python3
"""
Minimal TLS tunnel with SNI spoofing
Usage: python tunnel.py <remote_host> [local_port] [sni_hostname]
"""

import socket
import ssl
import select
import sys
import threading
import signal
import os
import subprocess

def tunnel(client, remote):
    """Bidirectional data forwarding"""
    sockets = [client, remote]
    bytes_sent = 0
    bytes_recv = 0

    while True:
        try:
            readable, _, exceptional = select.select(sockets, [], sockets, 300)

            if exceptional:
                print(f"[-] Socket error (sent: {bytes_sent}, recv: {bytes_recv})")
                return

            if not readable:
                continue

            for sock in readable:
                try:
                    data = sock.recv(32768)
                    if not data:
                        print(f"[-] Connection closed (sent: {bytes_sent}, recv: {bytes_recv})")
                        return

                    target = remote if sock is client else client
                    target.sendall(data)

                    if sock is client:
                        bytes_sent += len(data)
                    else:
                        bytes_recv += len(data)

                except Exception as e:
                    print(f"[-] Tunnel error: {e} (sent: {bytes_sent}, recv: {bytes_recv})")
                    return
        except KeyboardInterrupt:
            return
        except Exception as e:
            print(f"[-] Select error: {e}")
            return

def handle_client(client, remote_host, remote_port, sni):
    """Handle incoming client connection"""
    tls_sock = None
    try:
        # Set timeout for initial request
        client.settimeout(10)

        # Read CONNECT request
        request = b""
        while b"\r\n\r\n" not in request:
            chunk = client.recv(4096)
            if not chunk:
                print("[-] No CONNECT request received")
                return
            request += chunk

        # Remove timeout for data transfer
        client.settimeout(None)

        print(f"[+] Connection: {request.split(b' ')[1].decode()}")

        # Connect to remote with TLS + SNI spoofing
        sock = socket.socket()
        sock.settimeout(10)
        sock.connect((remote_host, remote_port))
        sock.settimeout(None)

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        tls_sock = ctx.wrap_socket(sock, server_hostname=sni)
        print(f"[+] TLS connected (SNI: {sni}, Cipher: {tls_sock.cipher()[0]})")

        # Send success to client
        client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        print("[+] Tunnel established")
        subprocess.run(["notify-send", "Tunnel", "Tunnel Established"]);

        # Start tunneling
        tunnel(client, tls_sock)
        print("[-] Tunnel closed")
        subprocess.run(["notify-send", "Tunnel", "Tunnel Closed", "-u", "critical"]);

    except socket.timeout:
        print("[!] Connection timeout")
    except Exception as e:
        print(f"[!] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            client.close()
        except:
            pass
        try:
            if tls_sock:
                tls_sock.close()
        except:
            pass

def main():
    if len(sys.argv) < 2:
        print("Usage: python tunnel.py <remote_host> [local_port] [sni_hostname]")
        print("Example: python tunnel.py 1.2.3.4 8080 google.com")
        sys.exit(1)

    remote_host = sys.argv[1]
    local_port = int(sys.argv[2]) if len(sys.argv) > 2 else 8080
    sni = sys.argv[3] if len(sys.argv) > 3 else "google.com"
    remote_port = 443

    # Create listening socket
    server = socket.socket()
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", local_port))
    server.listen(5)

    print(f"[*] Listening on 127.0.0.1:{local_port}")
    print(f"[*] Remote: {remote_host}:{remote_port} (SNI: {sni})")

    def cleanup(signum=None, frame=None):
        # Kill socks_monitor silently
        os.system("pkill -9 -f socks_monitor.py >/dev/null 2>&1")
        server.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    try:
        while True:
            client, addr = server.accept()
            print(f"[+] Client: {addr[0]}:{addr[1]}")
            threading.Thread(
                target=handle_client,
                args=(client, remote_host, remote_port, sni),
                daemon=True
            ).start()
    except KeyboardInterrupt:
        print("\n[*] Shutting down")
        cleanup()
    finally:
        server.close()
        cleanup()

if __name__ == "__main__":
    main()
