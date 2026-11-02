import os
import sys
import json
import time
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from .utils_logging import get_logger
from .paths import get_user_data_dir, get_lock_path, get_heartbeat_path

logger = get_logger("instance")

class InstanceManager:
    """
    Manages single-instance locking and crash/recovery heartbeats.
    """
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = data_dir or str(get_user_data_dir())
        os.makedirs(self.data_dir, exist_ok=True)
        self.lock_file = os.path.join(self.data_dir, "deskmate.lock") if data_dir else get_lock_path()
        self.heartbeat_file = os.path.join(self.data_dir, "heartbeat.json") if data_dir else get_heartbeat_path()
        self.lock_handle = None

    def acquire_lock(self) -> Tuple[bool, bool]:
        """
        Attempts to acquire single-instance lock.
        Returns: (is_acquired, unclean_previous_shutdown)
        """
        unclean_shutdown = False
        # Check if heartbeat file exists before locking
        if os.path.exists(self.heartbeat_file):
            try:
                with open(self.heartbeat_file, "r", encoding="utf-8") as f:
                    hb = json.load(f)
                # If heartbeat file was not marked gracefully exited
                if not hb.get("clean_exit", False):
                    unclean_shutdown = True
                    logger.warning(f"Unclean previous shutdown detected from heartbeat: {hb}")
            except Exception as e:
                unclean_shutdown = True
                logger.warning(f"Error reading heartbeat file: {e}")

        # Check existing lock file
        if os.path.exists(self.lock_file):
            try:
                with open(self.lock_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                old_pid = data.get("pid")
                # Check if process is still running
                if old_pid and self._is_pid_running(old_pid):
                    logger.error(f"Another instance of AI DeskMate is already running (PID {old_pid}).")
                    return False, False
                else:
                    logger.info(f"Stale lock file found for dead PID {old_pid}. Cleaning up.")
                    unclean_shutdown = True
            except Exception:
                unclean_shutdown = True

        # Write our lock file
        try:
            with open(self.lock_file, "w", encoding="utf-8") as f:
                json.dump({
                    "pid": os.getpid(),
                    "started_at": datetime.now().isoformat()
                }, f)
        except Exception as e:
            logger.error(f"Failed to create lock file: {e}")
            return False, False

        self.update_heartbeat(clean_exit=False)
        return True, unclean_shutdown

    def is_instance_running(self) -> bool:
        """Return True if a companion instance is actively running with valid PID."""
        if os.path.exists(self.lock_file):
            try:
                with open(self.lock_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                old_pid = data.get("pid")
                if old_pid and self._is_pid_running(old_pid):
                    return True
            except Exception:
                pass
        return False

    def _is_pid_running(self, pid: int) -> bool:
        if sys.platform == "win32":
            try:
                import psutil
                if psutil.pid_exists(pid):
                    proc = psutil.Process(pid)
                    if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                        return False
                    pname = proc.name().lower()
                    return "aideskmate" in pname or "python" in pname
                return False
            except Exception:
                try:
                    import ctypes
                    kernel32 = ctypes.windll.kernel32
                    process = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
                    if process:
                        exit_code = ctypes.c_ulong()
                        kernel32.GetExitCodeProcess(process, ctypes.byref(exit_code))
                        buf = ctypes.create_unicode_buffer(1024)
                        size = ctypes.c_ulong(1024)
                        kernel32.QueryFullProcessImageNameW(process, 0, buf, ctypes.byref(size))
                        kernel32.CloseHandle(process)
                        if exit_code.value == 259:
                            exe_name = buf.value.lower()
                            return "aideskmate" in exe_name or "python" in exe_name
                    return False
                except Exception:
                    return False
        else:
            try:
                import psutil
                if psutil.pid_exists(pid):
                    pname = psutil.Process(pid).name().lower()
                    return "aideskmate" in pname or "python" in pname
                return False
            except Exception:
                try:
                    os.kill(pid, 0)
                    return True
                except OSError:
                    return False

    def update_heartbeat(self, clean_exit: bool = False, extra_state: Optional[Dict[str, Any]] = None):
        """Writes current heartbeat."""
        payload = {
            "pid": os.getpid(),
            "timestamp": datetime.now().isoformat(),
            "last_tick": time.time(),
            "clean_exit": clean_exit
        }
        if extra_state:
            payload.update(extra_state)
        try:
            with open(self.heartbeat_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write heartbeat: {e}")

    def stop_running_instance(self) -> bool:
        """Terminates currently running companion instance if alive and releases lock."""
        stopped = False
        if os.path.exists(self.lock_file):
            try:
                with open(self.lock_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                old_pid = data.get("pid")
                if old_pid and self._is_pid_running(old_pid):
                    import psutil
                    proc = psutil.Process(old_pid)
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except Exception:
                        proc.kill()
                    stopped = True
            except Exception as e:
                logger.warning(f"Error terminating running instance: {e}")
            finally:
                self.release_lock()
        return stopped

    def release_lock(self):
        """Marks clean exit and cleans up lock."""
        self.update_heartbeat(clean_exit=True)
        try:
            if os.path.exists(self.lock_file):
                os.remove(self.lock_file)
        except Exception as e:
            logger.warning(f"Error removing lock file: {e}")
