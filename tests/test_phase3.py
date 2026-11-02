import os
import unittest
import tempfile
from datetime import datetime, timedelta

from app.db.database import DatabaseManager
from app.settings.config_manager import ConfigManager
from app.nudges.trigger_engine import TriggerEngine, NudgeDecision

class TestPhase3FlowAndDecisions(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_deskmate.db')
        self.config_path = os.path.join(self.temp_dir, 'test_config.json')

        self.db = DatabaseManager(self.db_path)
        self.config_mgr = ConfigManager(self.config_path)
        self.config_mgr.update({
            'flow_detection_enabled': True,
            'flow_keys_threshold': 120,
            'flow_window_minutes': 5,
            'idle_suppression_seconds': 300.0,
            'water_interval_minutes': 60,
            'posture_interval_minutes': 45,
            'eye_rest_interval_minutes': 20,
            'break_interval_minutes': 90,
            'energy_checkin_interval_minutes': 120,
            'mute_hours_enabled': False
        })
        self.trigger_engine = TriggerEngine(db_mgr=self.db, config_mgr=self.config_mgr)

    def test_flow_detection_delays_water_nudge(self):
        """When user has been typing fast, water nudge should be delayed rather than fired."""
        now = datetime.now()
        # Seed 5 minutes of high-speed typing into activity_log
        for i in range(5):
            self.db.log_activity(keys_per_min=150, mouse_events_per_min=20,
                                 active_window_title='Code Editor', active_process_name='code.exe',
                                 idle_seconds=1.0)

        # Set last water trigger 65 minutes ago (so it is due)
        self.trigger_engine.last_trigger_times['water_reminder'] = now - timedelta(minutes=65)

        state = {
            'continuous_active_min': 65.0,
            'continuous_typing_min': 10.0,
            'is_snoozed': False,
            'idle_seconds': 2.0,
            'keys_per_min': 160,
            'mouse_events_per_min': 15,
            'now_dt': now
        }

        decision = self.trigger_engine.should_nudge('water_reminder', state, now)
        self.assertFalse(decision.should_fire)
        self.assertEqual(decision.decision, 'delayed')
        self.assertEqual(decision.reason, 'in_flow_delayed')

    def test_flow_detection_delays_posture_and_eye_rest(self):
        """Posture check and eye rest should be delayed when in flow."""
        now = datetime.now()
        for i in range(5):
            self.db.log_activity(keys_per_min=140, mouse_events_per_min=10,
                                 active_window_title='Document', active_process_name='word.exe',
                                 idle_seconds=2.0)

        state = {
            'continuous_active_min': 30.0,
            'continuous_typing_min': 50.0,  # posture is due (>45)
            'is_snoozed': False,
            'idle_seconds': 1.0,
            'keys_per_min': 140,
            'now_dt': now
        }

        decision_posture = self.trigger_engine.should_nudge('posture_check', state, now)
        self.assertFalse(decision_posture.should_fire)
        self.assertEqual(decision_posture.decision, 'delayed')
        self.assertEqual(decision_posture.reason, 'in_flow_delayed')

        decision_eye = self.trigger_engine.should_nudge('eye_rest', state, now)
        self.assertFalse(decision_eye.should_fire)
        self.assertEqual(decision_eye.decision, 'delayed')
        self.assertEqual(decision_eye.reason, 'in_flow_delayed')

    def test_break_reminder_overrides_flow_state(self):
        """Break reminder (90+ min continuous active) is a hard override and must fire even in flow."""
        now = datetime.now()
        for i in range(5):
            self.db.log_activity(keys_per_min=180, mouse_events_per_min=30,
                                 active_window_title='Terminal', active_process_name='bash.exe',
                                 idle_seconds=0.5)

        state = {
            'continuous_active_min': 95.0,  # Break due (>90)
            'continuous_typing_min': 95.0,
            'is_snoozed': False,
            'idle_seconds': 0.5,
            'keys_per_min': 180,
            'now_dt': now
        }

        decision = self.trigger_engine.should_nudge('break_reminder', state, now)
        self.assertTrue(decision.should_fire)
        self.assertEqual(decision.decision, 'fired')
        self.assertEqual(decision.reason, 'fired')
        self.assertTrue(decision.metadata.get('hard_override', False))

    def test_idle_suppression_outright(self):
        """If user is idle for > 5 minutes (300s), all nudges are suppressed outright."""
        now = datetime.now()
        state = {
            'continuous_active_min': 120.0,
            'continuous_typing_min': 60.0,
            'is_snoozed': False,
            'idle_seconds': 350.0,  # Away > 5 minutes
            'keys_per_min': 0,
            'now_dt': now
        }

        for nudge_type in ['break_reminder', 'water_reminder', 'posture_check', 'eye_rest', 'energy_checkin']:
            decision = self.trigger_engine.should_nudge(nudge_type, state, now)
            self.assertFalse(decision.should_fire)
            self.assertEqual(decision.decision, 'suppressed')
            self.assertEqual(decision.reason, 'idle_suppressed')

    def test_nudge_decision_logging_fired_and_suppressed(self):
        """Every evaluation through check_triggers must be logged into nudge_decision_log."""
        now = datetime.now()
        # Non-flow state, break due
        trigger = self.trigger_engine.check_triggers(
            continuous_active_min=95.0,
            continuous_typing_min=20.0,
            is_snoozed=False,
            idle_seconds=5.0,
            keys_per_min=40,
            mouse_events_per_min=10,
            now_dt=now
        )

        self.assertIsNotNone(trigger)
        self.assertEqual(trigger[0], 'break_reminder')

        # Check DB log records
        decisions = self.db.get_recent_nudge_decisions(limit=20)
        self.assertGreaterEqual(len(decisions), 5)  # All 5 nudge types evaluated and logged

        # Check that we have both 'fired' and other decisions logged
        fired_types = [d['nudge_type'] for d in decisions if d['decision'] == 'fired']
        self.assertIn('break_reminder', fired_types)

        not_due_or_suppressed = [d for d in decisions if d['decision'] in ('not_due', 'suppressed', 'delayed')]
        self.assertTrue(len(not_due_or_suppressed) > 0)

        # Verify fields in decision log record
        sample = decisions[0]
        self.assertIn('nudge_type', sample)
        self.assertIn('decision', sample)
        self.assertIn('reason', sample)
        self.assertIn('keys_per_min', sample)
        self.assertIn('idle_seconds', sample)
        self.assertIn('is_in_flow', sample)

    def test_flow_sensitivity_toggle_live(self):
        """Disabling flow detection allows water/posture nudges to fire immediately."""
        now = datetime.now()
        for i in range(5):
            self.db.log_activity(keys_per_min=160, mouse_events_per_min=20,
                                 active_window_title='Code', active_process_name='code.exe',
                                 idle_seconds=1.0)

        # Disable flow detection
        self.config_mgr.set('flow_detection_enabled', False)
        self.trigger_engine.last_trigger_times['water_reminder'] = now - timedelta(minutes=65)

        state = {
            'continuous_active_min': 65.0,
            'continuous_typing_min': 10.0,
            'is_snoozed': False,
            'idle_seconds': 2.0,
            'keys_per_min': 160,
            'now_dt': now
        }

        decision = self.trigger_engine.should_nudge('water_reminder', state, now)
        self.assertTrue(decision.should_fire)
        self.assertEqual(decision.decision, 'fired')

if __name__ == '__main__':
    unittest.main()
