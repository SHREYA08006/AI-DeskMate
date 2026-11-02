"""
app/system/autostart.py - Windows Autostart Manager for AI DeskMate.

Manages automatic startup on user sign-in via the Windows Registry key:
HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run -> "AIDeskMate"
Provides idempotent enable, disable, and status query functions.
"""

import os
import sys
import logging
from typing import Optional
from ..paths import is_frozen

logger = logging.getLogger("deskmate.autostart")

REG_SUBKEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_APP_NAME = "AIDeskMate"


def is_autostart_enabled() -> bool:
    """Return True if AI DeskMate is configured to launch on Windows sign-in."""
    if not sys.platform.startswith("win"):
        return False

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY, 0, winreg.KEY_READ) as key:
            try:
                val, _ = winreg.QueryValueEx(key, REG_APP_NAME)
                return bool(val)
            except FileNotFoundError:
                return False
    except Exception as e:
        logger.debug(f"Failed to query autostart status: {e}")
        return False


def get_default_command() -> str:
    """Return the appropriate command string to launch AI DeskMate."""
    if is_frozen():
        exe_path = sys.executable
        return f'"{exe_path}"'
    else:
        python_exe = sys.executable
        main_py = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "main.py")
        return f'"{python_exe}" "{main_py}"'


def enable_autostart(app_path: Optional[str] = None) -> bool:
    """
    Register AI DeskMate in Windows Run registry key.
    Idempotent: updates the value if already present.
    """
    if not sys.platform.startswith("win"):
        logger.info("Autostart via registry is only supported on Windows.")
        return False

    command = app_path or get_default_command()

    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, REG_APP_NAME, 0, winreg.REG_SZ, command)
            logger.info(f"Autostart enabled with command: {command}")
            return True
    except Exception as e:
        logger.error(f"Failed to enable autostart in registry: {e}")
        return False


def disable_autostart() -> bool:
    """
    Remove AI DeskMate from Windows Run registry key.
    Idempotent: returns True if key was absent or successfully removed.
    """
    if not sys.platform.startswith("win"):
        return True

    try:
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_SUBKEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, REG_APP_NAME)
                logger.info("Autostart disabled.")
                return True
        except FileNotFoundError:
            # Already disabled
            return True
    except Exception as e:
        logger.error(f"Failed to disable autostart in registry: {e}")
        return False
