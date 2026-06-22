# 🎯 UNIFIED MAIL TOOLS - START HERE

## ✅ Everything in ONE Folder

All files are directly in this folder. No subfolders. Simple!

```
unified-mailer/
├── RUN-DESKTOP.bat  ← CLICK THIS for Desktop GUI
├── RUN-WEB.bat      ← CLICK THIS for Web Server
├── start.py         ← Main launcher
├── [All Python files directly in root]
└── [All data folders: config/, data/, results/]
```

---

## 🚀 Quick Start (Choose One)

### Option 1: Desktop GUI (Local)
**Just double-click:**
```
RUN-DESKTOP.bat
```
- Opens Tkinter window
- Works offline
- Fast & simple

### Option 2: Web Server (Browser)
**Just double-click:**
```
RUN-WEB.bat
```
- Opens in browser: `http://127.0.0.1:5000`
- Works on any device on your network
- Full-featured dashboard

### Option 3: Auto-Detect
```bash
python3 start.py
```
- Launches Desktop if available
- Falls back to Web Server

---

## 📂 What's Included

**Core Files (All in root folder):**
- `config.py` - Configuration
- `mailer.py` - Email sender
- `smtp_checker.py` - SMTP validator
- `smtp_client.py` - SMTP client
- `campaign_state.py` - Campaign management
- `recipient_ops.py` - Recipient handling
- `preview.py` - Email preview
- `rate_limiter.py` - Rate limiting
- `rotator.py` - Rotation logic

**Interfaces:**
- `gui_desktop.py` - Tkinter GUI
- `app_web.py` - Flask web server
- `cli.py` - Command-line interface

**Tools:**
- `madcatmailer.py` - Mass mailer
- `mailpass2smtp.py` - SMTP checker
- `get_safe_mails.py` - Email validator

**Data Folders (Created automatically):**
- `config/` - Configuration data
- `data/` - Data storage
- `results/` - Results files
- `templates/` - HTML templates for web

---

## ⚡ System Requirements

- **Python 3.8+** (download from python.org)
- **Windows/Linux/Mac** all supported

---

## 🔧 If Something Goes Wrong

**"Python not found":**
- Install Python 3.8+ from https://www.python.org/
- Make sure to check "Add Python to PATH"

**Desktop GUI won't open:**
- Use `RUN-WEB.bat` instead
- Or run `python3 start.py web`

**Port 5000 in use:**
- Edit `RUN-WEB.bat` and change port number
- Or kill the process: `netstat -ano | findstr :5000`

**Dependencies missing:**
- The batch files install them automatically
- Or manually: `python3 -m pip install colorama flask psutil requests`

---

## 📚 Full Documentation

See `README.md` for detailed documentation

See `QUICKSTART.md` for more examples

---

## ✨ That's It!

Just:
1. Double-click `RUN-DESKTOP.bat` OR `RUN-WEB.bat`
2. Wait for it to start
3. Use the interface

**Everything is in ONE folder. No subfolders. No mess.** 🎉

---

**Old folders preserved?**
Your original 3 folders are still in the parent directory:
- `mailer_app/`
- `mailtools-main/`
- `mailtools-main gui/`

You can delete them or move them elsewhere when ready. They're not used by this unified version.
