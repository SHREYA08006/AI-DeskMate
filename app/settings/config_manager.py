import json
import os
import random
from typing import Dict, Any, Optional
from ..db.database import DatabaseManager
from ..paths import get_config_path

DEFAULT_CONFIG: Dict[str, Any] = {
    'onboarding_completed': False,
    'user_name': 'Friend',
    'avatar_name': 'Mochi',
    'avatar_type': 'cat',
    'personality_tone': 'chill',
    'energy_checkin_interval_minutes': 120,
    'break_interval_minutes': 90,
    'water_interval_minutes': 60,
    'posture_interval_minutes': 45,
    'eye_rest_interval_minutes': 20,
    'tts_enabled': True,
    'screen_walk_enabled': True,
    'mute_hours_enabled': False,
    'mute_hours_start': '22:00',
    'mute_hours_end': '08:00',
    'flow_detection_enabled': True,
    'flow_keys_threshold': 120,
    'flow_window_minutes': 5,
    'idle_suppression_seconds': 300.0,
    'launch_on_startup': False,
    'enable_ml_fatigue_nudges': True,
    'ml_confidence_threshold': 0.6,
    'enable_adaptive_frequency': True,
    'min_frequency_multiplier': 0.5,
    'max_frequency_multiplier': 2.0
}

RANDOM_NAMES = {
    'cat': ['Mochi', 'Whiskers', 'Luna', 'Neko', 'Cleo', 'Simba', 'Milo', 'Kiki', 'Toby'],
    'dog': ['Barnaby', 'Buster', 'Daisy', 'Buddy', 'Rocky', 'Bailey', 'Charlie', 'Teddy', 'Rusty'],
    'hamster': ['Pip', 'Peanut', 'Nugget', 'Cheeks', 'Nibbles', 'Gizmo', 'Biscuit', 'Oat', 'Puff'],
    'human': ['Alex', 'Sam', 'Jordan', 'Taylor', 'Morgan', 'Riley', 'Casey', 'Avery', 'Robin'],
    'robot': ['Byte', 'Pixel', 'Sparky', 'Cosmo', 'Circuit', 'Nova', 'Bolt', 'Echo', 'Gizmo']
}

AVATAR_OPTIONS = [
    {'type': 'cat', 'name': 'Cat', 'emoji': '🐱', 'description': 'Curious, nimble & calming companion'},
    {'type': 'dog', 'name': 'Dog', 'emoji': '🐶', 'description': 'Loyal, energetic & encouraging buddy'},
    {'type': 'hamster', 'name': 'Hamster', 'emoji': '🐹', 'description': 'Cute, cheerful & cozy pocket pal'},
    {'type': 'human', 'name': 'Human Buddy', 'emoji': '🧑', 'description': 'Supportive, friendly peer co-worker'},
    {'type': 'robot', 'name': 'Robo-Buddy', 'emoji': '🤖', 'description': 'Precise, witty & futuristic assistant'}
]

PERSONALITY_TONES = [
    {'id': 'chill', 'name': 'Chill & Gentle', 'tagline': 'Calm, patient nudges that respect your flow.'},
    {'id': 'strict', 'name': 'Strict & Disciplined', 'tagline': 'Direct, no-nonsense accountability.'},
    {'id': 'cheerful', 'name': 'Cheerful & Upbeat', 'tagline': 'Enthusiastic, motivating and high energy!'},
    {'id': 'sarcastic', 'name': 'Witty & Sarcastic', 'tagline': 'Playful banter, clever remarks and jokes.'}
]

class ConfigManager:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or get_config_path()
        self._config: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._config = {**DEFAULT_CONFIG, **data}
            except Exception as e:
                print(f'Error reading config file: {e}. Falling back to defaults.')
                self._config = DEFAULT_CONFIG.copy()
        else:
            self._config = DEFAULT_CONFIG.copy()
            self.save()
        return self._config

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=4, ensure_ascii=False)
            
            # Sync key settings to SQLite database
            db = DatabaseManager.get_instance()
            for key, val in self._config.items():
                db.set_setting(key, str(val))
        except Exception as e:
            print(f'Error saving config: {e}')

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default if default is not None else DEFAULT_CONFIG.get(key))

    def set(self, key: str, value: Any, auto_save: bool = True):
        self._config[key] = value
        if auto_save:
            self.save()

    def update(self, updates: Dict[str, Any], auto_save: bool = True):
        self._config.update(updates)
        if auto_save:
            self.save()

    @staticmethod
    def get_random_name(avatar_type: str) -> str:
        names = RANDOM_NAMES.get(avatar_type.lower(), RANDOM_NAMES['cat'])
        return random.choice(names)
