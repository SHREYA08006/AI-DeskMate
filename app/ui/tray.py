import os
import sys
import time
import json
import webbrowser
import threading
import subprocess
from datetime import datetime
from typing import Optional, Callable, Any
from PIL import Image

from ..settings.config_manager import ConfigManager
from ..db.database import DatabaseManager
from ..avatar.avatar_manager import AvatarManager
from ..ml.predictor import FatiguePredictor
from ..utils_logging import get_logger
from ..paths import get_log_file_path, get_heartbeat_path, is_frozen
from ..dashboard.launcher import find_free_port

logger = get_logger("tray")

try:
    import pystray
    from pystray import MenuItem as item, Menu
    PYSTRAY_AVAILABLE = True
except ImportError:
    PYSTRAY_AVAILABLE = False
    logger.warning("pystray not installed. Running in headless mode.")

class TrayController:
    def __init__(self,
                 config_mgr: Optional[ConfigManager] = None,
                 db_mgr: Optional[DatabaseManager] = None,
                 avatar_mgr: Optional[AvatarManager] = None,
                 tracker: Optional[Any] = None,
                 on_check_energy: Optional[Callable[[], None]] = None,
                 on_open_settings: Optional[Callable[[], None]] = None,
                 on_test_nudge: Optional[Callable[[str], None]] = None,
                 on_trigger_sample_nudge: Optional[Callable[[], None]] = None,
                 on_quit: Optional[Callable[[], None]] = None,
                 is_demo: bool = False):
        self.config_mgr = config_mgr or ConfigManager()
        self.db_mgr = db_mgr or DatabaseManager.get_instance()
        self.avatar_mgr = avatar_mgr or AvatarManager()
        self.tracker = tracker
        self.on_check_energy = on_check_energy
        self.on_open_settings = on_open_settings
        self.on_test_nudge = on_test_nudge
        self.on_trigger_sample_nudge = on_trigger_sample_nudge
        self.on_quit = on_quit
        self.is_demo = is_demo
        self.predictor = FatiguePredictor.get_instance(demo=is_demo)

        self.icon = None
        self._snooze_until: Optional[float] = None
        self._streamlit_proc: Optional[subprocess.Popen] = None

    def snooze_all(self, minutes: int = 60):
        self._snooze_until = time.time() + (minutes * 60)
        logger.info(f"Snoozed all nudges for {minutes} minutes.")

    def clear_snooze(self):
        self._snooze_until = None
        logger.info("Cleared nudge snooze.")

    def is_snoozed(self) -> bool:
        if self._snooze_until is None:
            return False
        if time.time() > self._snooze_until:
            self._snooze_until = None
            return False
        return True

    def open_dashboard(self):
        def _launch():
            try:
                port = find_free_port()
                url = f"http://127.0.0.1:{port}"

                cmd = [sys.executable]
                if is_frozen():
                    cmd.extend(["--dashboard", "--port", str(port)])
                else:
                    cmd.extend(["-m", "app.dashboard.launcher", "--port", str(port)])

                if self.is_demo:
                    cmd.append("--demo")

                cmd.append("--no-browser")

                self._streamlit_proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                time.sleep(2.0)
                webbrowser.open(url)
            except Exception as e:
                logger.error(f"Error launching Streamlit dashboard: {e}")

        t = threading.Thread(target=_launch, daemon=True, name='DashboardLauncher')
        t.start()

    def show_system_health(self):
        """Displays system health dialog and info."""
        def _show():
            try:
                import tkinter as tk
                from tkinter import messagebox
                
                db_size_kb = round(self.db_mgr.get_database_size_bytes() / 1024.0, 1)
                model_status = self.predictor.status
                tracker_status = "Running" if (self.tracker and self.tracker._running) else "Active"
                
                hb_path = get_heartbeat_path()
                last_hb = "Unknown"
                if os.path.exists(hb_path):
                    try:
                        with open(hb_path, "r", encoding="utf-8") as f:
                            hb_data = json.load(f)
                            last_hb = hb_data.get("timestamp", "Unknown")[:19]
                    except Exception:
                        pass

                log_file = get_log_file_path()
                mode_str = "Demo (Synthetic)" if self.is_demo else "Normal (Live)"
                msg = (
                    f"AI DeskMate — System Health\n\n"
                    f"• Mode: {mode_str}\n"
                    f"• Activity Tracker: {tracker_status}\n"
                    f"• Database Size: {db_size_kb} KB\n"
                    f"• Fatigue Model: {model_status.upper()}\n"
                    f"• Last Heartbeat: {last_hb}\n"
                    f"• Log File: {log_file}\n"
                )
                
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                messagebox.showinfo("System Health", msg)
                root.destroy()
            except Exception as e:
                logger.error(f"Error showing system health: {e}")

        t = threading.Thread(target=_show, daemon=True)
        t.start()

    def open_log_file(self):
        log_path = get_log_file_path()
        if os.path.exists(log_path):
            try:
                if sys.platform == 'win32':
                    os.startfile(log_path)
                else:
                    subprocess.Popen(['xdg-open', log_path])
            except Exception as e:
                logger.error(f"Error opening log file: {e}")

    def _create_image(self):
        icon_path = self.avatar_mgr.get_tray_icon_path()
        if os.path.exists(icon_path):
            return Image.open(icon_path)
        img = Image.new('RGB', (64, 64), color='#3B8ED0')
        return img

    def run(self):
        if not PYSTRAY_AVAILABLE:
            logger.info("pystray not available. Tray controller running headless.")
            return

        avatar_name = self.config_mgr.get('avatar_name', 'DeskMate')
        header_text = f"🧪 [Demo] AI DeskMate ({avatar_name})" if self.is_demo else f"AI DeskMate ({avatar_name})"

        menu_items = [
            item(header_text, lambda: None, enabled=False),
            Menu.SEPARATOR,
            item('📊 Open Dashboard', lambda: self.open_dashboard()),
            item('⚡ Check Energy Now', lambda: self.on_check_energy() if self.on_check_energy else None),
            item('🏥 System Health', lambda: self.show_system_health()),
            item('📄 Open Log File', lambda: self.open_log_file()),
        ]

        if self.is_demo and self.on_trigger_sample_nudge:
            menu_items.extend([
                Menu.SEPARATOR,
                item('🎭 Trigger Sample Nudge', lambda: self.on_trigger_sample_nudge()),
            ])

        menu_items.extend([
            Menu.SEPARATOR,
            item('🚶 Walk Across Screen (Break Test)', lambda: self.on_test_walk() if self.on_test_walk else (self.on_test_nudge('break_reminder') if self.on_test_nudge else None)),
            item('💧 Water Reminder Test', lambda: self.on_test_nudge('water_reminder') if self.on_test_nudge else None),
            item('🧘 Posture Check Test', lambda: self.on_test_nudge('posture_check') if self.on_test_nudge else None),
            item('👀 Eye Rest (20-20-20) Test', lambda: self.on_test_nudge('eye_rest') if self.on_test_nudge else None),
            item('🚶 Break Reminder Test', lambda: self.on_test_nudge('break_reminder') if self.on_test_nudge else None),
            Menu.SEPARATOR,
            item('⏸️ Snooze All (1h)', lambda: self.snooze_all(60)),
            item('▶️ Resume Nudges', lambda: self.clear_snooze()),
            item('⚙️ Settings & Companion Profile', lambda: self.on_open_settings() if self.on_open_settings else None),
            Menu.SEPARATOR,
            item('❌ Quit AI DeskMate', lambda: self._quit())
        ])

        menu = Menu(*menu_items)
        image = self._create_image()
        self.icon = pystray.Icon('ai_deskmate', image, title=f'AI DeskMate - {avatar_name}', menu=menu)
        self.icon.run()

    def _quit(self):
        if self._streamlit_proc:
            try:
                self._streamlit_proc.terminate()
            except Exception:
                pass
        if self.icon:
            self.icon.stop()
        if self.on_quit:
            self.on_quit()

    def stop(self):
        if self._streamlit_proc:
            try:
                self._streamlit_proc.terminate()
            except Exception:
                pass
            self._streamlit_proc = None
        if self.icon:
            self.icon.stop()
