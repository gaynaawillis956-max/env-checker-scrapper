#!/bin/bash
# Launch Unified Mail Tools - Auto-detect mode or specify
# Usage: ./launch.sh [desktop|web]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-auto}"

echo ""
echo "========================================"
echo "  Unified Mail Tools"
echo "========================================"
echo ""

# Check Python 3
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi

# Install dependencies
echo "Installing dependencies..."
python3 -m pip install -q -r "$SCRIPT_DIR/requirements.txt"

# Run
if [ "$MODE" = "web" ]; then
    echo "Starting Web Server..."
    echo ""
    echo "Open your browser to: http://127.0.0.1:5000"
    echo ""
    python3 "$SCRIPT_DIR/run.py" --mode web
elif [ "$MODE" = "desktop" ]; then
    echo "Starting Desktop GUI..."
    python3 "$SCRIPT_DIR/run.py" --mode desktop
else
    echo "Starting in auto-detect mode..."
    python3 "$SCRIPT_DIR/run.py" --mode auto
fi
