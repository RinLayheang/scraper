#!/usr/bin/env bash
# ==============================================================================
# KCMS Collaborative Labeler - Server Start Script (macOS / Linux / Git Bash)
# ==============================================================================

set -e

# Resolve script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect Python
if command -v python3 &>/dev/null; then
    PYTHON_CMD="python3"
elif command -v python &>/dev/null; then
    PYTHON_CMD="python"
elif command -v py &>/dev/null; then
    PYTHON_CMD="py"
else
    echo "❌ Error: Python is not installed or not in PATH."
    exit 1
fi

# Locate run.py
if [ -f "$SCRIPT_DIR/run.py" ]; then
    RUN_PATH="$SCRIPT_DIR/run.py"
elif [ -f "$SCRIPT_DIR/labeling_app/run.py" ]; then
    RUN_PATH="$SCRIPT_DIR/labeling_app/run.py"
else
    echo "❌ Error: Could not locate run.py in $SCRIPT_DIR."
    exit 1
fi

# Check for Cloudflare Tunnel tool
if command -v cloudflared &>/dev/null; then
    echo "☁️  Cloudflare CLI detected."
elif command -v npx &>/dev/null; then
    echo "☁️  Cloudflare available via npx."
else
    echo "ℹ️  Cloudflare not found. (Install with: brew install cloudflared)"
fi

echo "🚀 Starting KCMS Collaborative Labeler..."
exec $PYTHON_CMD "$RUN_PATH" "$@"
