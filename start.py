#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Mail Tools - Single Folder Version
Launch as Desktop GUI or Web Server
"""
import sys
import os
import socket

# Set working directory to script location
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

def is_port_in_use(port):
    """Check if port is already in use"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex(('127.0.0.1', port))
        return result == 0
    finally:
        sock.close()

def launch_desktop():
    """Launch Desktop GUI"""
    try:
        print("[*] Loading Desktop Interface...\n")
        import tkinter as tk
        from gui_desktop import MailerApp

        print("[*] Starting Tkinter window...\n")
        app = MailerApp()
        app.mainloop()
    except ImportError as e:
        print(f"[!] Tkinter not available: {e}")
        print("[!] Falling back to Web Interface...\n")
        launch_web()
    except Exception as e:
        print(f"[!] Error launching desktop: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def launch_web(host="127.0.0.1", port=5000):
    """Launch Web Server"""
    try:
        # Check if port is in use
        if is_port_in_use(port):
            print(f"[!] Port {port} is already in use")
            print(f"[*] Try a different port: python3 start.py web --port 8080")
            sys.exit(1)

        print(f"[*] Loading Web Server...\n")
        from app_web import app, logger

        print(f"[*] Starting Flask server...\n")
        logger.info(f"Web server starting on {host}:{port}")

        print(f"    Open: http://{host}:{port}")
        print(f"    (Ctrl+C to stop)\n")

        app.run(host=host, port=port, debug=False, use_reloader=False, threaded=True)
    except Exception as e:
        print(f"[!] Error launching web server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def main():
    # Parse arguments
    mode = "auto"
    port = 5000
    host = "127.0.0.1"

    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

    if len(sys.argv) > 2 and sys.argv[2] == "--port" and len(sys.argv) > 3:
        try:
            port = int(sys.argv[3])
        except ValueError:
            print(f"[!] Invalid port: {sys.argv[3]}")
            sys.exit(1)

    # Launch in requested mode
    if mode == "desktop":
        launch_desktop()
    elif mode == "web":
        launch_web(host, port)
    elif mode == "auto":
        # Try desktop, fall back to web
        try:
            import tkinter
            launch_desktop()
        except ImportError:
            print("[!] Desktop mode not available (Tkinter not found)")
            print("[*] Launching Web Server instead...\n")
            launch_web(host, port)
    else:
        print(f"[!] Unknown mode: {mode}")
        print("Usage: python3 start.py [desktop|web|auto] [--port PORT]")
        sys.exit(1)

if __name__ == "__main__":
    main()
