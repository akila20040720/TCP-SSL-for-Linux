# TLS Tunnel 


A lightweight, fast, and minimal toolchain with built-in SOCKS5 proxy and traffic monitoring.



---

## 📌 Overview

This project provides a **secure tunneling solution** that combines:

* **TLS encryption**
* **Domain Masking**
* **SOCKS5 proxy support**


---


## 📁 Project Structure

```id="t7q9cn"
.
├── tunnel.py         # TLS tunnel 
├── socks_monitor.py  # SOCKS5 proxy + monitoring
├── tunnel.sh         # Start/stop tunnel
├── status.sh         # View stats & performance
├── tunnel.conf       # Configuration file
```

---

## ⚙️ Installation Guide

### 1. Clone Repository

```bash id="wq9l8c"
git clone <your-repo-url>
cd <your-project-folder>
```

### 2. Set Permissions

```bash id="k1v9rt"
chmod +x tunnel.sh status.sh
```

### 3. Requirements

* Python 3.x
* Linux / macOS (or WSL)

Check Python:

```bash id="6cv1s2"
python3 --version
```

---

## 🧪 Usage (Step-by-Step)

### Step 1: Configure Tunnel

```bash id="8i4h2k"
nano tunnel.conf
```

---

### Step 2: Start TLS Tunnel

With monitoring:

```bash id="d2nvw7"
./tunnel.sh tunnel.conf
```

Without monitoring:

```bash id="l9z3x1"
./tunnel.sh tunnel.conf --no-monitor
```

---

### Step 3: Connect via SOCKS5 Proxy

```bash id="x3m7ks"
curl --socks5 127.0.0.1:2070 https://example.com
```

You can also use:

* Web browsers (Chrome, Firefox)
* Postman
* System proxy settings

---

### Step 4: Monitor Tunnel Status

```bash id="h3n8ak"
./status.sh            # Full stats
./status.sh speed      # Speed only
./status.sh --watch    # Live monitoring
```

---

## 🧾 Configuration File (`tunnel.conf`)

```ini id="7m2vqp"
REMOTE_HOST=<server_address>
SSH_USER=<username>
SSH_PASS=<password>
SSH_PORT=<server_port>

TUNNEL_PORT=9090
SOCKS_PORT=2070

SNI=google.lk

EXPIRES=2025-12-31
BLOCKLIST=/path/to/blocklist.txt
```

---

## 🚫 Blocklist (Ad Blocking Support)

Supported formats:

```id="q8m2ke"
0.0.0.0 ads.example.com
127.0.0.1 tracker.example.com
example.com
```

* Ignore lines starting with `#`
* Improves performance and privacy

🔗 Recommended blocklist:
https://github.com/zachlagden/Pi-hole-Optimized-Blocklists

---



## 🛠 Troubleshooting Guide

### ❌ Port Already in Use

```bash id="czx81u"
lsof -i :2070
kill -9 <PID>
```

---

### ❌ Tunnel Not Connecting

* Verify `REMOTE_HOST` and `SSH_PORT`
* Check username/password
* Ensure SSH access is enabled on server

---

### ⚠️ Slow Speed Fix

* Reduce blocklist size
* Check network stability

---

## 📌 Best Practices

* Keep blocklist optimized
* Monitor usage regularly for performance tuning

---

## ⚠️ Legal Disclaimer

This project is for:


* Research and development

🚫 Do NOT use for:

* Illegal activities
* Bypassing organizational policies without permission

---


## 🤝 Contributing

Pull requests are welcome!
For major changes, open an issue first to discuss improvements.

---



## ❤️ Support

If this project helped you:

* ⭐ Star the repository
* 🍴 Fork and improve
* 🧑‍💻 Share with others

---
