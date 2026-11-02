import json
import os
import random
from typing import Dict, Any, Optional, List
from ..settings.config_manager import ConfigManager
from ..paths import get_nudge_messages_path


class TemplateEngine:
    def __init__(self, templates_path: Optional[str] = None, config_mgr: Optional[ConfigManager] = None):
        self.templates_path = templates_path or get_nudge_messages_path()
        self.config_mgr = config_mgr or ConfigManager()
        self.templates: Dict[str, Dict[str, List[str]]] = {}
        self.load_templates()

    def load_templates(self):
        if os.path.exists(self.templates_path):
            try:
                with open(self.templates_path, 'r', encoding='utf-8') as f:
                    self.templates = json.load(f)
            except Exception as e:
                print(f'Error loading nudge templates from {self.templates_path}: {e}')
                self.templates = {}
        else:
            print(f'Warning: Templates file {self.templates_path} not found.')

    def render(self, nudge_type: str, tone: Optional[str] = None, **kwargs) -> str:
        current_tone = tone or self.config_mgr.get('personality_tone', 'chill')
        user_name = kwargs.get('user_name', self.config_mgr.get('user_name', 'Friend'))
        avatar_name = kwargs.get('avatar_name', self.config_mgr.get('avatar_name', 'DeskMate'))
        
        context = {
            'user_name': user_name,
            'avatar_name': avatar_name,
            'minutes': kwargs.get('minutes', 60),
            'hours': kwargs.get('hours', 1),
            **kwargs
        }

        # Check if nudge_type exists
        type_templates = self.templates.get(nudge_type, {})
        # Get list of messages for the given tone or fallback to 'chill' or first available
        tone_templates = type_templates.get(current_tone)
        if not tone_templates and 'chill' in type_templates:
            tone_templates = type_templates['chill']
        elif not tone_templates and type_templates:
            tone_templates = next(iter(type_templates.values()))

        if not tone_templates:
            # Fallback default message
            return f'Hey {user_name}, it\'s {avatar_name} checking in!'

        # Pick a random variant
        raw_template = random.choice(tone_templates)

        # Format template with context, silently handling any missing keys
        try:
            return raw_template.format(**context)
        except Exception:
            class SafeDict(dict):
                def __missing__(self, key):
                    return f'{{{key}}}'
            return raw_template.format_map(SafeDict(context))
