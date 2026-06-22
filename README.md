# Unified Mail Tools v2.0

A merged mail application combining **Desktop GUI (Tkinter)** and **Web Interface (Flask)**.

Features:
- ✅ Desktop GUI (Tkinter) - local use
- ✅ Web Server (Flask) - remote/server deployment  
- ✅ Bulk email sending
- ✅ SMTP validation
- ✅ Email filtering
- ✅ Campaign management

## Installation

### Prerequisites
- **Python 3.8+**
- Works on Windows, Linux, macOS, VPS, RDP servers

### Setup

```bash
cd unified-mailer
pip install -r requirements.txt
```

---

## Usage

### Option 1: Auto-Detect (Recommended)
Automatically launches Desktop GUI if display available, otherwise Web Server:

```bash
python3 run.py
```

### Option 2: Desktop GUI (Tkinter)

**Windows:**
```bash
launch-desktop.bat
```

**Linux/macOS:**
```bash
./launch.sh desktop
# or
python3 run.py --mode desktop
```

**Features:**
- Local Tkinter interface
- Real-time email sending
- Campaign management
- Built-in previews
- Configuration UI

### Option 3: Web Server (Flask)

**Windows:**
```bash
launch-web.bat
```

**Linux/macOS:**
```bash
./launch.sh web
# or
python3 run.py --mode web --port 5000
```

**Access:**
- Local:   `http://127.0.0.1:5000`
- Network: `http://<your-ip>:5000`

**Features:**
- Browser-based interface
- Deploy on VPS/RDP
- Remote access via network
- Reverse proxy ready (Nginx, Cloudflare)
- Live dashboard & logs

---

## Configuration

### Web Server Config (`web/config.json`)
```json
{
  "port": 5000,
  "host": "0.0.0.0",
  "proxy_fix": false
}
```

### Environment Variables
```bash
# Windows
set PORT=8080 && python3 run.py --mode web

# Linux
PORT=8080 python3 run.py --mode web
```

---

## Deployed on Server (Linux/VPS)

### Using Systemd Service

Create `/etc/systemd/system/mailtools.service`:
```ini
[Unit]
Description=Unified Mail Tools
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/unified-mailer
ExecStart=/usr/bin/python3 run.py --mode web --host 0.0.0.0 --port 5000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable & start:
```bash
sudo systemctl enable mailtools
sudo systemctl start mailtools
sudo systemctl status mailtools
```

### Reverse Proxy (Nginx)

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass         http://127.0.0.1:5000;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
    }
}
```

---

## Directory Structure

```
unified-mailer/
├── run.py                 # Main entry point
├── requirements.txt       # Dependencies
├── launch-desktop.bat     # Windows desktop launcher
├── launch-web.bat         # Windows web launcher
├── launch.sh              # Linux launcher
│
├── core/                  # Shared business logic
│   ├── config.py
│   ├── mailer.py
│   ├── smtp_checker.py
│   ├── smtp_client.py
│   ├── recipient_ops.py
│   ├── preview.py
│   ├── campaign_state.py
│   └── rate_limiter.py
│
├── desktop/               # Tkinter GUI
│   ├── gui.py            # Main Tkinter interface
│   └── launch.py         # Desktop launcher
│
├── web/                   # Flask web server
│   ├── app.py            # Flask application
│   ├── config.json       # Web config
│   └── templates/        # HTML templates
│       └── index.html
│
├── tools/                 # External tools
│   ├── madcatmailer.py   # Mass mailer
│   ├── mailpass2smtp.py  # SMTP checker
│   └── get_safe_mails.py # Email validator
│
└── logs/                  # Application logs
    └── mailtools.log
```

---

## Troubleshooting

**Desktop GUI won't launch:**
- Ensure `tkinter` is installed: `python3 -m tkinter`
- On Linux: `sudo apt install python3-tk`

**Web server port in use:**
- Change port: `python3 run.py --mode web --port 8080`
- Or: `set PORT=8080 && python3 run.py --mode web`

**Dependencies missing:**
- Reinstall: `pip install --upgrade -r requirements.txt`

**Import errors:**
- Ensure you're in the `unified-mailer` directory
- Add to PYTHONPATH: `export PYTHONPATH=$PWD:$PYTHONPATH`

---

## Development

To add features or modify:
1. Edit `core/` modules (shared logic)
2. Edit `desktop/gui.py` (Tkinter changes)
3. Edit `web/app.py` (Flask changes)
4. Test both modes: `--mode desktop` and `--mode web`

---

## License

Same as original mailer_app and mailtools-main projects.
