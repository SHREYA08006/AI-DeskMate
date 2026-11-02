import time
import threading
import sys
import psutil
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from ..db.database import DatabaseManager
from ..utils_logging import get_logger

logger = get_logger("tracker")

try:
    from pynput import keyboard, mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    logger.warning("pynput not installed. Activity tracking will run in mock mode.")

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except ImportError:
    PYGETWINDOW_AVAILABLE = False

if sys.platform == 'win32':
    try:
        import win32gui
        import win32process
        WIN32_AVAILABLE = True
    except ImportError:
        WIN32_AVAILABLE = False
else:
    WIN32_AVAILABLE = False

def get_active_window_info() -> Tuple[str, str]:
    title = 'Unknown'
    process_name = 'Unknown'
    
    if sys.platform == 'win32' and WIN32_AVAILABLE:
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                title = win32gui.GetWindowText(hwnd) or 'Desktop/Idle'
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid > 0:
                    try:
                        proc = psutil.Process(pid)
                        process_name = proc.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        process_name = 'System'
        except Exception as e:
            logger.debug(f"Error fetching active window: {e}")
    elif PYGETWINDOW_AVAILABLE:
        try:
            active = gw.getActiveWindow()
            if active and active.title:
                title = active.title
        except Exception as e:
            logger.debug(f"Error fetching window: {e}")

    return title, process_name

class ActivityTracker:
    def __init__(self,
                 db_manager: Optional[DatabaseManager] = None,
                 interval_seconds: int = 60,
                 afk_break_threshold_sec: float = 180.0,
                 sleep_gap_threshold_sec: float = 180.0,
                 resume_grace_period_sec: float = 180.0):
        self.db = db_manager or DatabaseManager.get_instance()
        self.interval_seconds = interval_seconds
        self.afk_break_threshold_sec = afk_break_threshold_sec  # default 180s (3m, matches features.py)
        self.sleep_gap_threshold_sec = sleep_gap_threshold_sec  # default 180s (gap > 3x interval means sleep/suspend)
        self.resume_grace_period_sec = resume_grace_period_sec  # 3 min grace period after sleep resume

        self._key_count = 0
        self._mouse_count = 0
        self._last_event_time = time.time()
        self._last_tick_time = time.time()
        self._last_resume_time = 0.0
        self._lock = threading.Lock()

        # Continuous streak tracking
        self._continuous_active_sec = 0.0
        self._continuous_typing_sec = 0.0
        self._time_since_last_break_sec = 0.0
        
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._keyboard_listener = None
        self._mouse_listener = None

    def _on_key_press(self, key):
        try:
            with self._lock:
                self._key_count += 1
                self._last_event_time = time.time()
        except Exception as e:
            logger.debug(f"Key event error: {e}")

    def _on_mouse_move(self, x, y):
        try:
            with self._lock:
                self._mouse_count += 1
                self._last_event_time = time.time()
        except Exception as e:
            logger.debug(f"Mouse move error: {e}")

    def _on_mouse_click(self, x, y, button, pressed):
        if pressed:
            try:
                with self._lock:
                    self._mouse_count += 1
                    self._last_event_time = time.time()
            except Exception as e:
                logger.debug(f"Mouse click error: {e}")

    def _on_mouse_scroll(self, x, y, dx, dy):
        try:
            with self._lock:
                self._mouse_count += 1
                self._last_event_time = time.time()
        except Exception as e:
            logger.debug(f"Mouse scroll error: {e}")

    def start(self):
        if self._running:
            return

        self._running = True
        self._last_event_time = time.time()
        self._last_tick_time = time.time()

        if PYNPUT_AVAILABLE:
            try:
                self._keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
                self._keyboard_listener.daemon = True
                self._keyboard_listener.start()

                self._mouse_listener = mouse.Listener(
                    on_move=self._on_mouse_move,
                    on_click=self._on_mouse_click,
                    on_scroll=self._on_mouse_scroll
                )
                self._mouse_listener.daemon = True
                self._mouse_listener.start()
            except Exception as e:
                logger.error(f'Error starting input listeners: {e}')

        self._worker_thread = threading.Thread(target=self._log_loop, daemon=True, name='ActivityTrackerWorker')
        self._worker_thread.start()
        logger.info("ActivityTracker started.")

    def stop(self):
        self._running = False
        if self._keyboard_listener:
            try:
                self._keyboard_listener.stop()
            except Exception:
                pass
        if self._mouse_listener:
            try:
                self._mouse_listener.stop()
            except Exception:
                pass
        logger.info("ActivityTracker stopped.")

    def handle_resume_from_sleep(self, gap_seconds: float):
        """Called when a suspension or long gap is detected."""
        logger.info(f"System resume/gap detected ({gap_seconds:.1f}s gap). Resetting streaks and activating grace period.")
        with self._lock:
            self._continuous_active_sec = 0.0
            self._continuous_typing_sec = 0.0
            self._time_since_last_break_sec = 0.0
            self._key_count = 0
            self._mouse_count = 0
            self._last_event_time = time.time()
            self._last_tick_time = time.time()
            self._last_resume_time = time.time()

        try:
            self.db.log_recovery_event('sleep_resume', f'Detected system suspend/wake gap of {gap_seconds:.1f}s')
        except Exception as e:
            logger.warning(f"Failed to log sleep recovery event: {e}")

    def is_in_resume_grace_period(self, now_time: Optional[float] = None) -> bool:
        """Returns True if tracker is within post-sleep grace period."""
        now = now_time or time.time()
        with self._lock:
            if self._last_resume_time <= 0.0:
                return False
            return (now - self._last_resume_time) < self.resume_grace_period_sec

    def _log_loop(self):
        while self._running:
            try:
                time.sleep(self.interval_seconds)
                if not self._running:
                    break

                now = time.time()
                time_since_last_tick = now - self._last_tick_time

                # Detect sleep/wake or system pause gap
                if time_since_last_tick > self.sleep_gap_threshold_sec:
                    self.handle_resume_from_sleep(time_since_last_tick)
                    self._last_tick_time = now
                    continue

                self._process_interval_tick(now, time_since_last_tick)
                self._last_tick_time = now

            except Exception as e:
                logger.error(f"Unexpected error in ActivityTracker log loop: {e}", exc_info=True)
                time.sleep(2.0)

    def _process_interval_tick(self, now: float, elapsed_sec: float):
        """Processes one aggregation tick with AFK and streak calculations."""
        with self._lock:
            keys = self._key_count
            mouse_events = self._mouse_count
            idle = max(0.0, now - self._last_event_time)

            # AFK & Break handling (consistent with features.py: idle >= 180s / 3m counts as break)
            if idle >= self.afk_break_threshold_sec:
                self._continuous_active_sec = 0.0
                self._continuous_typing_sec = 0.0
                self._time_since_last_break_sec = 0.0
            else:
                self._continuous_active_sec += elapsed_sec
                self._time_since_last_break_sec += elapsed_sec

                if keys > 5:
                    self._continuous_typing_sec += elapsed_sec
                elif idle > 180.0:
                    self._continuous_typing_sec = 0.0

            # Reset interval counters
            self._key_count = 0
            self._mouse_count = 0

        window_title, process_name = get_active_window_info()

        try:
            self.db.log_activity(
                keys_per_min=keys,
                mouse_events_per_min=mouse_events,
                active_window_title=window_title,
                active_process_name=process_name,
                idle_seconds=round(idle, 1)
            )
        except Exception as e:
            logger.error(f"Error logging activity: {e}")

    def flush_partial_minute(self):
        """Flushes any currently aggregated keystrokes and mouse events immediately."""
        now = time.time()
        with self._lock:
            keys = self._key_count
            mouse_events = self._mouse_count
            idle = max(0.0, now - self._last_event_time)
            self._key_count = 0
            self._mouse_count = 0
        window_title, process_name = get_active_window_info()
        try:
            self.db.log_activity(
                keys_per_min=keys,
                mouse_events_per_min=mouse_events,
                active_window_title=window_title,
                active_process_name=process_name,
                idle_seconds=round(idle, 1)
            )
            logger.info("Flushed partial minute activity on recovery/shutdown.")
        except Exception as e:
            logger.error(f"Failed to flush partial minute: {e}")

    def get_current_stats(self) -> Dict[str, Any]:
        with self._lock:
            now_t = time.time()
            idle = max(0.0, now_t - self._last_event_time)
            keys = self._key_count
            mouse = self._mouse_count
            cont_active_min = round(self._continuous_active_sec / 60.0, 1)
            cont_typing_min = round(self._continuous_typing_sec / 60.0, 1)
            time_since_break_min = round(self._time_since_last_break_sec / 60.0, 1)
            in_grace = False
            if self._last_resume_time > 0.0:
                in_grace = (now_t - self._last_resume_time) < self.resume_grace_period_sec

        window_title, process_name = get_active_window_info()
        return {
            'keys_in_current_interval': keys,
            'mouse_in_current_interval': mouse,
            'idle_seconds': round(idle, 1),
            'continuous_active_minutes': cont_active_min,
            'continuous_typing_minutes': cont_typing_min,
            'time_since_last_break_min': time_since_break_min,
            'in_resume_grace_period': in_grace,
            'active_window_title': window_title,
            'active_process_name': process_name
        }

    def reset_streaks(self):
        with self._lock:
            self._continuous_active_sec = 0.0
            self._continuous_typing_sec = 0.0
            self._time_since_last_break_sec = 0.0
            logger.info("Streaks reset manually.")
