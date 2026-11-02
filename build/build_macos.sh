#!/usr/bin/env bash
# build/build_macos.sh - Best-Effort macOS .app Bundle Script for AI DeskMate
#
# IMPORTANT NOTICE:
# This script is provided as a best-effort build pipeline. Because development and
# primary QA were conducted on Windows, macOS builds must be manually verified on a Mac.
#
# macOS System Permissions Required:
# 1. Accessibility: (System Settings > Privacy & Security > Accessibility)
#    Required by `pynput` to listen for global key press and mouse move events.
# 2. Input Monitoring: (System Settings > Privacy & Security > Input Monitoring)
#    Required on macOS Catalina (10.15)+ for background process keystroke listening.
# 3. Screen Recording / Accessibility:
#    Required to read frontmost application process names and window titles.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "=========================================================="
echo "   AI DESKMATE -- macOS BUNDLE BUILD SCRIPT (BEST-EFFORT)"
echo "=========================================================="

APP_VERSION=$(cat VERSION 2>/dev/null || echo "1.0.0")
echo "Building AI DeskMate v${APP_VERSION} for macOS..."

# Check virtual environment
if [ -d ".venv" ]; then
    PYTHON=".venv/bin/python"
    PYINSTALLER=".venv/bin/pyinstaller"
else
    PYTHON="python3"
    PYINSTALLER="pyinstaller"
fi

# Run tests
echo "Running automated test suite..."
"$PYTHON" -m unittest tests.test_phase9

# Build .app using PyInstaller
echo "Compiling .app bundle via PyInstaller..."
"$PYINSTALLER" \
    --name="AIDeskMate" \
    --windowed \
    --noconfirm \
    --distpath="dist" \
    --workpath="build/temp_macos" \
    --add-data="nudge_messages.json:." \
    --add-data="insight_messages.json:." \
    --add-data="VERSION:." \
    --add-data="assets:assets" \
    --hidden-import="pynput" \
    --hidden-import="pystray" \
    --hidden-import="pyttsx3" \
    --hidden-import="customtkinter" \
    --hidden-import="sklearn" \
    --hidden-import="joblib" \
    --collect-all="streamlit" \
    --collect-all="customtkinter" \
    app/main.py

echo "macOS build finished. Output available in dist/AIDeskMate.app"
echo "Remember to grant Accessibility and Input Monitoring permissions in macOS Settings!"
