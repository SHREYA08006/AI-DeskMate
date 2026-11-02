"""
app/paths.py - Packaging-Safe Path Resolution and First-Run Management for AI DeskMate.

Provides unified path resolution supporting:
1. Source mode vs. Frozen executable mode (PyInstaller sys._MEIPASS).
2. Per-user data directory isolation (%APPDATA% on Windows, Application Support on macOS, ~/.local/share on Linux).
3. First-run directory bootstrapping, default configuration creation, and avatar asset verification.
4. Demo mode database and artifact redirection.
"""

import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("deskmate.paths")


def is_frozen() -> bool:
    """Return True if running inside a PyInstaller frozen bundle."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_bundle_dir() -> Path:
    """
    Return the root directory of bundled read-only resources.
    In frozen mode: sys._MEIPASS.
    In source mode: repository root (parent of 'app').
    """
    if is_frozen():
        return Path(getattr(sys, '_MEIPASS')).resolve()
    # Source mode: app/paths.py -> app -> repo root
    return Path(__file__).resolve().parent.parent


def get_user_data_dir() -> Path:
    """
    Return the per-user writable data directory.
    Respects DESKMATE_DATA_DIR environment variable for test isolation.
    Windows: %APPDATA%/AI DeskMate
    macOS: ~/Library/Application Support/AI DeskMate
    Linux: ~/.local/share/ai-deskmate (or $XDG_DATA_HOME/ai-deskmate)
    """
    custom_dir = os.environ.get("DESKMATE_DATA_DIR")
    if custom_dir:
        return Path(custom_dir).resolve()

    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata)
        else:
            base = Path.home() / "AppData" / "Roaming"
        return base / "AI DeskMate"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "AI DeskMate"
    else:
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            base = Path(xdg_data)
        else:
            base = Path.home() / ".local" / "share"
        return base / "ai-deskmate"


def ensure_user_data_dir() -> Path:
    """
    Ensure the user data directory and its subdirectories exist.
    Initializes default config and directories if missing.
    """
    data_dir = get_user_data_dir()
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "logs").mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning(f"Could not create user data directory {data_dir}: {e}")
    return data_dir


def get_db_path(demo: bool = False) -> str:
    """Return absolute path to SQLite database (deskmate.db or demo.db)."""
    filename = "demo.db" if demo else "deskmate.db"
    return str(get_user_data_dir() / filename)


def get_config_path() -> str:
    """Return absolute path to config.json in user data directory."""
    return str(get_user_data_dir() / "config.json")


def get_log_dir() -> str:
    """Return absolute path to logs directory in user data directory."""
    return str(get_user_data_dir() / "logs")


def get_log_file_path() -> str:
    """Return absolute path to deskmate.log in user data directory."""
    return str(get_user_data_dir() / "logs" / "deskmate.log")


def get_lock_path() -> str:
    """Return absolute path to process lockfile in user data directory."""
    return str(get_user_data_dir() / "deskmate.lock")


def get_heartbeat_path() -> str:
    """Return absolute path to heartbeat.json in user data directory."""
    return str(get_user_data_dir() / "heartbeat.json")


def get_model_path(demo: bool = False) -> str:
    """Return absolute path to fatigue model joblib binary."""
    filename = "demo_fatigue_model.joblib" if demo else "fatigue_model.joblib"
    return str(get_user_data_dir() / filename)


def get_model_metadata_path(demo: bool = False) -> str:
    """Return absolute path to model metadata json."""
    filename = "demo_model_metadata.json" if demo else "model_metadata.json"
    return str(get_user_data_dir() / filename)


def get_dataset_path(filename: str, demo: bool = False) -> str:
    """Return absolute path to a dataset file (e.g. training_data.csv)."""
    prefix = "demo_" if demo else ""
    return str(get_user_data_dir() / f"{prefix}{filename}")


# Bundled read-only resources

def get_resource_path(relative_path: str) -> str:
    """Return absolute path to a bundled read-only resource file."""
    return str(get_bundle_dir() / relative_path)


def get_nudge_messages_path() -> str:
    """Return absolute path to bundled nudge_messages.json."""
    return get_resource_path("nudge_messages.json")


def get_insight_messages_path() -> str:
    """Return absolute path to bundled insight_messages.json."""
    return get_resource_path("insight_messages.json")


def get_version_path() -> str:
    """Return absolute path to VERSION file."""
    return get_resource_path("VERSION")


def get_version() -> str:
    """Read version string from VERSION file, defaulting to '1.0.0'."""
    version_file = get_version_path()
    if os.path.exists(version_file):
        try:
            with open(version_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return "1.0.0"


def get_assets_dir() -> str:
    """
    Return path to assets directory.
    Prefers bundled read-only assets directory. If not present, falls back to user data assets.
    """
    bundled_assets = get_bundle_dir() / "assets"
    if bundled_assets.exists():
        return str(bundled_assets)
    user_assets = get_user_data_dir() / "assets"
    try:
        user_assets.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning(f"Could not create user assets directory {user_assets}: {e}")
    return str(user_assets)


def get_avatars_dir() -> str:
    """Return path to avatars directory within assets."""
    return os.path.join(get_assets_dir(), "avatars")


def is_first_run() -> bool:
    """Return True if this is the first run (no config or onboarding not completed)."""
    config_file = get_config_path()
    if not os.path.exists(config_file):
        return True
    try:
        import json
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return not data.get("onboarding_completed", False)
    except Exception:
        return True
