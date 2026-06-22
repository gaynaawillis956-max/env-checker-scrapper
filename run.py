#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Mail Tools - Desktop & Web Interface
Supports both Tkinter GUI and Flask Web Server
"""
import sys
import argparse
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    parser = argparse.ArgumentParser(
        prog="unified-mailer",
        description="Bulk Mail Tools - Desktop GUI or Web Interface",
    )
    parser.add_argument(
        "--mode",
        choices=["desktop", "web", "auto"],
        default="auto",
        help="Launch mode: desktop (Tkinter), web (Flask), or auto-detect"
    )
    parser.add_argument("--port", type=int, default=5000, help="Web server port (default: 5000)")
    parser.add_argument("--host", default="0.0.0.0", help="Web server host (default: 0.0.0.0)")

    args = parser.parse_args()

    mode = args.mode

    # Auto-detect mode
    if mode == "auto":
        try:
            import tkinter
            mode = "desktop"
        except ImportError:
            mode = "web"

    if mode == "desktop":
        print("[*] Launching Desktop Interface (Tkinter)...")
        launch_desktop()
    else:
        print("[*] Launching Web Interface (Flask)...")
        launch_web(args.host, args.port)


def launch_desktop():
    """Launch Tkinter desktop GUI"""
    try:
        from desktop.gui import launch
        launch()
    except Exception as e:
        print(f"[!] Error launching desktop GUI: {e}")
        sys.exit(1)


def launch_web(host="0.0.0.0", port=5000):
    """Launch Flask web interface"""
    try:
        from web.app import app, logger

        logger.info(f"Starting web server on {host}:{port}")
        print(f"\n[✓] Web server starting...")
        print(f"    Local:   http://127.0.0.1:{port}")
        print(f"    Network: http://{host}:{port}\n")

        app.run(host=host, port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"[!] Error launching web server: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
