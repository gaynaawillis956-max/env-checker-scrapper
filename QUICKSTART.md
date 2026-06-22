# Unified Mail Tools - Quick Start Guide

## 🎉 What Was Merged

✅ **mailer_app** (Desktop GUI - Tkinter)  
✅ **mailtools-main** (Web Server - Flask)  
✅ **All Tools** (SMTP Checker, Mass Mailer, Email Validator)

**Result:** Single application that runs as either **Desktop GUI** or **Web Server**

---

## 🚀 Quick Start

### Option 1: Auto-Detect (Recommended)
```bash
cd unified-mailer
python3 run.py
```
→ Launches **Desktop GUI** if available, otherwise **Web Server**

### Option 2: Force Desktop GUI
```bash
launch-desktop.bat          # Windows
./launch.sh desktop         # Linux/macOS
```

### Option 3: Force Web Server
```bash
launch-web.bat              # Windows
./launch.sh web             # Linux/macOS
```

---

## 📋 What's Inside

```
unified-mailer/
├── core/              ← Shared logic (SMTP, mailer, config)
├── desktop/           ← Tkinter GUI
├── web/               ← Flask web server
├── tools/             ← External tools (madcatmailer, etc)
├── run.py             ← Main entry point
├── requirements.txt   ← Dependencies
├── launch-desktop.bat ← Desktop launcher (Windows)
├── launch-web.bat     ← Web launcher (Windows)
└── launch.sh          ← Unix launcher
```

---

## 💻 Desktop Mode (Windows/Linux/Mac)

**Pros:**
- Local GUI (no browser)
- Tkinter-based (lightweight)
- Full featured

**How to Launch:**
```bash
python3 run.py --mode desktop
# or
launch-desktop.bat
```

---

## 🌐 Web Mode (Server/Cloud/RDP)

**Pros:**
- Browser-based (any device)
- Remote access
- Deploy on VPS/RDP
- Reverse proxy ready

**How to Launch:**
```bash
python3 run.py --mode web
# or
launch-web.bat
```

**Access:**
- Local: `http://127.0.0.1:5000`
- Network: `http://<your-ip>:5000`

---

## ⚙️ Configuration

### Desktop (Tkinter)
- Configure via GUI interface
- Settings saved in config files

### Web (Flask)
Edit `web/config.json`:
```json
{
  "port": 5000,
  "host": "0.0.0.0",
  "proxy_fix": false
}
```

Or use environment variables:
```bash
PORT=8080 python3 run.py --mode web
```

---

## 📦 Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run
python3 run.py
```

---

## 🔧 Troubleshooting

**Desktop GUI won't launch:**
- Ensure tkinter is installed: `python3 -m tkinter`
- On Linux: `sudo apt install python3-tk`

**Web server port in use:**
```bash
python3 run.py --mode web --port 8080
```

**Import errors:**
```bash
# Make sure you're in the right directory
cd unified-mailer
export PYTHONPATH=$PWD:$PYTHONPATH
python3 run.py
```

---

## 📚 Full Documentation

See `README.md` for detailed documentation, deployment guides, and advanced configuration.

---

## ✨ Features Merged

From **mailer_app:**
- ✅ Tkinter Desktop GUI
- ✅ CLI interface
- ✅ Bulk mailer
- ✅ SMTP validation
- ✅ Campaign state management
- ✅ Email preview

From **mailtools-main:**
- ✅ Flask Web Interface
- ✅ Live dashboard
- ✅ madcatmailer (mass mailer)
- ✅ mailpass2smtp (SMTP checker)
- ✅ get_safe_mails (email validator)
- ✅ Real-time logs
- ✅ Reverse proxy support

---

## 🎯 Next Steps

1. **Desktop User?** → Run `launch-desktop.bat` or `./launch.sh desktop`
2. **Server Deployment?** → Run `launch-web.bat` or `./launch.sh web`
3. **Not sure?** → Run `python3 run.py` (auto-detects)

---

**Happy Mailing! 📧**
