import threading
import queue
import time
from typing import Optional

from ..settings.config_manager import ConfigManager

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False

class TTSEngine:
    _instance = None
    _lock = threading.Lock()

    def __init__(self, config_mgr: Optional[ConfigManager] = None):
        self.config_mgr = config_mgr or ConfigManager()
        self.speech_queue = queue.Queue()
        self._running = True
        self._worker_thread = threading.Thread(target=self._speech_loop, daemon=True, name='TTSWorker')
        self._worker_thread.start()

    @classmethod
    def get_instance(cls, config_mgr: Optional[ConfigManager] = None) -> 'TTSEngine':
        with cls._lock:
            if cls._instance is None:
                cls._instance = TTSEngine(config_mgr)
            return cls._instance

    def speak(self, text: str, force: bool = False):
        if not PYTTSX3_AVAILABLE:
            return

        if not force and not self.config_mgr.get('tts_enabled', False):
            return

        self.speech_queue.put(text)

    def _speech_loop(self):
        if not PYTTSX3_AVAILABLE:
            return

        while self._running:
            try:
                text = self.speech_queue.get(timeout=1.0)
                if text:
                    self._process_speech(text)
                    self.speech_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                print(f'TTS error: {e}')

    def _process_speech(self, text: str):
        try:
            engine = pyttsx3.init()
            engine.setProperty('rate', 170)
            engine.setProperty('volume', 0.9)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f'Error speaking text: {e}')

    def stop(self):
        self._running = False
