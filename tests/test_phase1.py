import os
import unittest
import tempfile
import json
import sqlite3
import time

from app.db.database import DatabaseManager
from app.settings.config_manager import ConfigManager
from app.nudges.template_engine import TemplateEngine
from app.tracker.activity_tracker import ActivityTracker
from app.avatar.avatar_manager import AvatarManager

class TestPhase1(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, 'test_deskmate.db')
        self.config_path = os.path.join(self.test_dir, 'test_config.json')
        self.db = DatabaseManager(self.db_path)
        self.config_mgr = ConfigManager(self.config_path)
        self.template_engine = TemplateEngine(config_mgr=self.config_mgr)

    def test_database_logging(self):
        row_id = self.db.log_activity(
            keys_per_min=120,
            mouse_events_per_min=45,
            active_window_title='Visual Studio Code',
            active_process_name='Code.exe',
            idle_seconds=2.5
        )
        self.assertIsNotNone(row_id)
        recent = self.db.get_recent_activity(limit=5)
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]['keys_per_min'], 120)
        self.assertEqual(recent[0]['active_process_name'], 'Code.exe')

        e_id = self.db.log_energy(energy_level=4, prompt_type='test_prompt', notes='Feeling good')
        self.assertIsNotNone(e_id)
        recent_e = self.db.get_recent_energy(limit=5)
        self.assertEqual(len(recent_e), 1)
        self.assertEqual(recent_e[0]['energy_level'], 4)

        n_id = self.db.log_nudge(nudge_type='break_reminder', message='Stretch time', action='acted')
        self.assertIsNotNone(n_id)

    def test_config_manager(self):
        self.config_mgr.set('user_name', 'Taylor')
        self.config_mgr.set('avatar_name', 'Pip')
        self.config_mgr.set('avatar_type', 'hamster')
        self.config_mgr.set('personality_tone', 'cheerful')

        new_mgr = ConfigManager(self.config_path)
        self.assertEqual(new_mgr.get('user_name'), 'Taylor')
        self.assertEqual(new_mgr.get('avatar_name'), 'Pip')
        self.assertEqual(new_mgr.get('personality_tone'), 'cheerful')

    def test_template_engine_personalization(self):
        rendered = self.template_engine.render(
            'break_reminder',
            tone='chill',
            user_name='Sam',
            avatar_name='Whiskers',
            minutes=90
        )
        self.assertIn('Sam', rendered)
        self.assertIn('Whiskers', rendered)
        self.assertTrue(len(rendered) > 10)

        sarcastic_msg = self.template_engine.render(
            'water_reminder',
            tone='sarcastic',
            user_name='Sam',
            avatar_name='Whiskers'
        )
        self.assertIn('Sam', sarcastic_msg)
        self.assertIn('Whiskers', sarcastic_msg)


    def test_avatar_assets_generation(self):
        avatar_mgr = AvatarManager(avatars_dir=os.path.join(self.test_dir, 'avatars'))
        cat_alert = avatar_mgr.get_avatar_image_path('cat', state='alert')
        self.assertIsNotNone(cat_alert)
        self.assertTrue(os.path.exists(cat_alert))

    def test_activity_tracker_simulation(self):
        tracker = ActivityTracker(db_manager=self.db, interval_seconds=1)
        tracker._on_key_press(None)
        tracker._on_key_press(None)
        tracker._on_mouse_move(10, 20)
        stats = tracker.get_current_stats()
        self.assertEqual(stats['keys_in_current_interval'], 2)
        self.assertEqual(stats['mouse_in_current_interval'], 1)

if __name__ == '__main__':
    unittest.main()
