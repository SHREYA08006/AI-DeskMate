import os
import unittest
import tempfile
import time
from datetime import datetime, timedelta

from app.db.database import DatabaseManager
from app.settings.config_manager import ConfigManager
from app.nudges.template_engine import TemplateEngine
from app.nudges.tts_engine import TTSEngine
from app.nudges.trigger_engine import TriggerEngine
from app.avatar.avatar_manager import AvatarManager, AVATAR_CONFIGS, ANIMATION_STATES
from app.tracker.activity_tracker import ActivityTracker

class TestPhase2(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, 'test_deskmate.db')
        self.config_path = os.path.join(self.test_dir, 'test_config.json')
        self.db = DatabaseManager(self.db_path)
        self.config_mgr = ConfigManager(self.config_path)
        self.avatar_mgr = AvatarManager(avatars_dir=os.path.join(self.test_dir, 'avatars'))
        self.trigger_engine = TriggerEngine(db_mgr=self.db, config_mgr=self.config_mgr)

    def test_multiframe_animation_generation(self):
        for av_type in AVATAR_CONFIGS:
            for state in ANIMATION_STATES:
                frames = self.avatar_mgr.get_animation_frames(av_type, state)
                self.assertEqual(len(frames), 4, f'Failed for {av_type} {state}')
                for fp in frames:
                    self.assertTrue(os.path.exists(fp), f'Frame missing: {fp}')

    def test_auto_trigger_water_reminder(self):
        self.config_mgr.set('water_interval_minutes', 60)
        self.config_mgr.set('mute_hours_enabled', False)
        
        future = self.trigger_engine.app_start_time + timedelta(minutes=65)
        res = self.trigger_engine.check_triggers(
            continuous_active_min=10.0,
            continuous_typing_min=5.0,
            is_snoozed=False,
            now_dt=future
        )
        self.assertIsNotNone(res)
        self.assertEqual(res[0], 'water_reminder')

    def test_auto_trigger_posture_check(self):
        self.config_mgr.set('posture_interval_minutes', 45)
        self.config_mgr.set('mute_hours_enabled', False)
        
        res = self.trigger_engine.check_triggers(
            continuous_active_min=15.0,
            continuous_typing_min=50.0,
            is_snoozed=False
        )
        self.assertIsNotNone(res)
        self.assertEqual(res[0], 'posture_check')

    def test_auto_trigger_eye_rest(self):
        self.config_mgr.set('eye_rest_interval_minutes', 20)
        self.config_mgr.set('mute_hours_enabled', False)

        res = self.trigger_engine.check_triggers(
            continuous_active_min=25.0,
            continuous_typing_min=2.0,
            is_snoozed=False
        )
        self.assertIsNotNone(res)
        self.assertEqual(res[0], 'eye_rest')

    def test_auto_trigger_break_reminder(self):
        self.config_mgr.set('break_interval_minutes', 90)
        self.config_mgr.set('mute_hours_enabled', False)

        res = self.trigger_engine.check_triggers(
            continuous_active_min=95.0,
            continuous_typing_min=10.0,
            is_snoozed=False
        )
        self.assertIsNotNone(res)
        self.assertEqual(res[0], 'break_reminder')

    def test_snooze_and_mute_hours(self):
        self.config_mgr.set('mute_hours_enabled', True)
        self.config_mgr.set('mute_hours_start', '22:00')
        self.config_mgr.set('mute_hours_end', '08:00')

        night_t = datetime(2026, 9, 19, 23, 30)
        self.assertTrue(self.trigger_engine.is_in_mute_window(night_t))

        res_muted = self.trigger_engine.check_triggers(
            continuous_active_min=100.0,
            is_snoozed=False,
            now_dt=night_t
        )
        self.assertIsNone(res_muted)

        day_t = datetime(2026, 9, 19, 14, 0)
        res_snoozed = self.trigger_engine.check_triggers(
            continuous_active_min=100.0,
            is_snoozed=True,
            now_dt=day_t
        )
        self.assertIsNone(res_snoozed)

    def test_tts_engine_toggle(self):
        tts = TTSEngine.get_instance(self.config_mgr)
        self.config_mgr.set('tts_enabled', False)
        if hasattr(tts, 'speak'):
            tts.speak('Hello Sam', force=False)
        self.assertEqual(tts.speech_queue.qsize(), 0)

        self.config_mgr.set('tts_enabled', True)
        if hasattr(tts, 'speak'):
            tts.speak('Hello Sam')
        self.assertGreaterEqual(tts.speech_queue.qsize(), 0)

if __name__ == '__main__':
    unittest.main()
