"""
app/dashboard/launcher.py - Dedicated Dashboard Launcher for AI DeskMate.

Launches the Streamlit analytics dashboard bound exclusively to localhost (127.0.0.1)
on an dynamically allocated free port, supporting both frozen PyInstaller executables
and development source mode.
"""

import os
import sys
import time
import socket
import logging
import argparse
import webbrowser
from pathlib import Path

from ..paths import get_bundle_dir, get_db_path, is_frozen

logger = logging.getLogger("deskmate.dashboard_launcher")


def find_free_port() -> int:
    """Find and return an available ephemeral TCP port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def get_dashboard_script_path() -> str:
    """Return the absolute path to the dashboard entry script.
    In a frozen PyInstaller build the resources are placed under the
    ``_internal`` directory (e.g. ``_internal/app/dashboard/dashboard.py``).
    This function first tries the standard location (``app/dashboard/dashboard.py``)
    and, if not found, falls back to the ``_internal`` layout used by the
    current executable.
    """
    if is_frozen():
        # Standard frozen layout (when the spec bundles the whole package)
        base = get_bundle_dir()
        candidate = base / "app" / "dashboard" / "dashboard.py"
        if candidate.exists():
            return str(candidate)
        # Fallback for the layout where PyInstaller extracts everything under
        # ``_internal`` (the current distribution uses this layout).
        candidate = base / "_internal" / "app" / "dashboard" / "dashboard.py"
        if candidate.exists():
            return str(candidate)
        # As a last resort look for a top‑level ``dashboard.py`` next to the
        # bundle root (rare but harmless).
        return str(base / "dashboard.py")
    else:
        # Development mode – script is alongside this file.
        return str(Path(__file__).resolve().parent / "dashboard.py")
    """Return the absolute path to app/dashboard/dashboard.py."""
    if is_frozen():
        base = get_bundle_dir()
        candidate = base / "app" / "dashboard" / "dashboard.py"
        if candidate.exists():
            return str(candidate)
        return str(base / "dashboard.py")
    else:
        return str(Path(__file__).resolve().parent / "dashboard.py")


def launch_dashboard(port: int = None, demo: bool = False, open_browser: bool = True):
    """Run Streamlit dashboard programmatically via streamlit.web.bootstrap."""
    if port is None or port <= 0:
        port = find_free_port()

    script_path = get_dashboard_script_path()
    if not os.path.exists(script_path):
        raise FileNotFoundError(f"Dashboard script not found at {script_path}")

    # Set environment variables for dashboard process
    if demo:
        os.environ["DESKMATE_DEMO_MODE"] = "1"
    else:
        os.environ.pop("DESKMATE_DEMO_MODE", None)

    flag_options = {
        'server.port': port,
        'server.address': '127.0.0.1',
        'server.headless': True,
        'server.runOnSave': False,
        'browser.serverAddress': '127.0.0.1',
        'browser.gatherUsageStats': False,
        'global.developmentMode': False
    }

    url = f"http://127.0.0.1:{port}"
    logger.info(f"Launching Streamlit dashboard on {url} (demo={demo})...")

    if open_browser:
        import threading
        def _open():
            time.sleep(1.5)
            try:
                webbrowser.open(url)
            except Exception as e:
                logger.warning(f"Failed to auto-open browser: {e}")
        threading.Thread(target=_open, daemon=True).start()

    import streamlit.web.bootstrap as bootstrap
    import streamlit.config as st_config

    bootstrap.load_config_options(flag_options)
    st_config.set_option('server.port', port)
    st_config.set_option('server.address', '127.0.0.1')
    st_config.set_option('server.headless', True)

    cli_args = ["--demo"] if demo else []
    bootstrap.run(script_path, is_hello=False, args=cli_args, flag_options=flag_options)


def run_selftest(demo: bool = False):
    """Run dashboard script through Streamlit's AppTest inside the frozen exe and exit non-zero on any exception."""
    if demo:
        os.environ["DESKMATE_DEMO_MODE"] = "1"
    else:
        os.environ.pop("DESKMATE_DEMO_MODE", None)

    script_path = get_dashboard_script_path()
    print(f"[SELFTEST] Running Streamlit AppTest on {script_path} (demo={demo})...")

    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(script_path, default_timeout=30)
    at.run(timeout=30)

    print(f"[SELFTEST] App execution finished.")
    if at.exception:
        print(f"[SELFTEST FAILED] {len(at.exception)} unhandled exceptions detected:")
        for exc in at.exception:
            print(f"  ERROR: {exc.value}")
        sys.exit(1)

    print(f"[SELFTEST PASSED] 0 exceptions encountered.")
    if demo:
        print(f"[SELFTEST] Found {len(at.info)} info badge(s):")
        for info in at.info:
            print(f"  Demo badge text: {info.value}")
    sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="AI DeskMate Streamlit Dashboard Launcher")
    parser.add_argument("--port", type=int, default=None, help="TCP port to bind Streamlit server")
    parser.add_argument("--demo", action="store_true", help="Launch in demo mode using demo.db")
    parser.add_argument("--no-browser", action="store_true", help="Do not automatically open browser")
    parser.add_argument("--selftest", action="store_true", help="Run dashboard through Streamlit AppTest and exit")

    args, unknown = parser.parse_known_args()
    if args.selftest:
        run_selftest(demo=args.demo)
        return

    launch_dashboard(port=args.port, demo=args.demo, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
