"""
run.py - Quick Start Launcher for AI DeskMate.
Usage:
    python run.py               -> Launches the Streamlit Dashboard at http://localhost:8501
    python -m app.main          -> Also launches the Streamlit Dashboard at http://localhost:8501
    python -m app.main --companion -> Launches desktop avatar companion directly without dashboard
"""
import sys

if __name__ == '__main__':
    from app.main import main
    main()
