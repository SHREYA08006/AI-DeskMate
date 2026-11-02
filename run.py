"""
run.py - Quick Start Launcher for AI DeskMate.
Opens the Streamlit Analytics & Companion Command Center in your browser.
From there, configure/choose your companion and click 'Start Avatar Companion' to start the desktop avatar.
"""
import sys

if __name__ == '__main__':
    from app.main import main
    main()
