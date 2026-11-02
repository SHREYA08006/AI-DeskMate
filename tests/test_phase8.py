import os
import json
import time
import unittest
import tempfile
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from app.db.database import DatabaseManager
from app.tracker.activity_tracker import ActivityTracker
from app.instance_manager import InstanceManager
from app.ml.predictor import FatiguePredictor
from app.dashboard.insights import generate_insights, render_insight_template

class TestPhase8RobustnessAndInsights(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_deskmate.db')
        self.db = DatabaseManager(self.db_path)

    def test_sleep_wake_resume_resets_streaks_and_applies_grace_period(self):
        """Test resume-from-sleep resets streaks and sets the nudge grace period."""
        tracker = ActivityTracker(
            db_manager=self.db,
            interval_seconds=1,
            sleep_gap_threshold_sec=5.0,
            resume_grace_period_sec=10.0
        )
        # Simulate active streaks
        tracker._continuous_active_sec = 7200.0  # 2 hours
        tracker._continuous_typing_sec = 3600.0  # 1 hour
        self.assertFalse(tracker.is_in_resume_grace_period())

        # Simulate waking from sleep with a 600s gap
        tracker.handle_resume_from_sleep(gap_seconds=600.0)

        stats = tracker.get_current_stats()
        self.assertEqual(stats['continuous_active_minutes'], 0.0)
        self.assertEqual(stats['continuous_typing_minutes'], 0.0)
        self.assertEqual(stats['time_since_last_break_min'], 0.0)
        self.assertTrue(stats['in_resume_grace_period'])

        # Check recovery log in database
        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recovery_log WHERE event_type = 'sleep_resume'")
            rows = cursor.fetchall()
            self.assertEqual(len(rows), 1)

    def test_long_afk_treated_as_break_consistently(self):
        """Test long AFK resets continuous active and sets time_since_last_break to 0."""
        tracker = ActivityTracker(
            db_manager=self.db,
            interval_seconds=1,
            afk_break_threshold_sec=180.0  # 3 min matches features.py
        )
        tracker._continuous_active_sec = 3600.0
        now = time.time()
        # Set last event time to 200s ago (AFK > 180s)
        tracker._last_event_time = now - 200.0

        tracker._process_interval_tick(now=now, elapsed_sec=1.0)
        stats = tracker.get_current_stats()
        self.assertEqual(stats['continuous_active_minutes'], 0.0)
        self.assertEqual(stats['time_since_last_break_min'], 0.0)

    def test_unclean_shutdown_detection_and_deduplication(self):
        """Test crash detection via InstanceManager and deduplication in DatabaseManager."""
        inst_mgr = InstanceManager(data_dir=self.temp_dir)
        # Create an unclean heartbeat file
        with open(inst_mgr.heartbeat_file, 'w', encoding='utf-8') as f:
            json.dump({'pid': 999999, 'timestamp': datetime.now().isoformat(), 'clean_exit': False}, f)

        acquired, unclean = inst_mgr.acquire_lock()
        self.assertTrue(acquired)
        self.assertTrue(unclean)
        inst_mgr.release_lock()

        # Test timestamp deduplication in database
        t_str = "2026-10-12 12:00:00"
        id1 = self.db.log_activity(keys_per_min=50, mouse_events_per_min=10, active_window_title="Doc", active_process_name="winword.exe", idle_seconds=0.0, timestamp=t_str)
        id2 = self.db.log_activity(keys_per_min=50, mouse_events_per_min=10, active_window_title="Doc", active_process_name="winword.exe", idle_seconds=0.0, timestamp=t_str)
        self.assertEqual(id1, id2)

    def test_single_instance_guard(self):
        """Test that a second instance cannot acquire lock when active PID holds it."""
        inst1 = InstanceManager(data_dir=self.temp_dir)
        acquired1, _ = inst1.acquire_lock()
        self.assertTrue(acquired1)

        # Second instance
        inst2 = InstanceManager(data_dir=self.temp_dir)
        acquired2, _ = inst2.acquire_lock()
        self.assertFalse(acquired2)

        inst1.release_lock()

    def test_tracker_survives_exception_in_loop(self):
        """Test that an unexpected exception does not crash the tracker."""
        tracker = ActivityTracker(db_manager=self.db, interval_seconds=1)
        # Inject error into db.log_activity
        def broken_log(*args, **kwargs):
            raise RuntimeError("Database simulated failure")

        tracker.db.log_activity = broken_log
        # Process tick directly; should catch and log instead of raising
        tracker._process_interval_tick(now=time.time(), elapsed_sec=1.0)
        self.assertFalse(tracker._running)  # tracker wasn't started so still False, but didn't crash

    def test_corrupted_model_fallback(self):
        """Test corrupted model joblib and column mismatch fall back cleanly."""
        bad_model_path = os.path.join(self.temp_dir, 'bad_model.joblib')
        bad_meta_path = os.path.join(self.temp_dir, 'bad_meta.json')

        # 1. Corrupted file (random garbage bytes)
        with open(bad_model_path, 'wb') as f:
            f.write(b"NOT_A_VALID_JOBLIB_FILE_CORRUPTED")
        with open(bad_meta_path, 'w', encoding='utf-8') as f:
            json.dump({'feature_columns': ['hour_of_day']}, f)

        pred = FatiguePredictor(model_path=bad_model_path, metadata_path=bad_meta_path)
        self.assertFalse(pred.is_available())
        self.assertEqual(pred.status, "corrupted")

        res = pred.predict_fatigue({'continuous_active_min': 50})
        self.assertFalse(res.available)

        # 2. Column mismatch
        import joblib
        from sklearn.dummy import DummyClassifier
        joblib.dump(DummyClassifier(), bad_model_path)
        with open(bad_meta_path, 'w', encoding='utf-8') as f:
            json.dump({'feature_columns': ['only_one_col']}, f)

        pred_mismatch = FatiguePredictor(model_path=bad_model_path, metadata_path=bad_meta_path)
        self.assertFalse(pred_mismatch.is_available())
        self.assertEqual(pred_mismatch.status, "column_mismatch")

    def test_insights_minimum_data_guards(self):
        """Test that insights return nothing when data is below threshold."""
        empty_act = pd.DataFrame()
        empty_en = pd.DataFrame()
        empty_nudge = pd.DataFrame()
        empty_dec = pd.DataFrame()

        insights = generate_insights(empty_act, empty_en, empty_nudge, empty_dec)
        self.assertEqual(insights, [])

        # Slightly insufficient data
        sparse_act = pd.DataFrame([{'timestamp': '2026-10-12 10:00:00', 'keys_per_min': 100, 'mouse_events_per_min': 20, 'idle_seconds': 0.0}])
        insights_sparse = generate_insights(sparse_act, empty_en, empty_nudge, empty_dec)
        self.assertEqual(insights_sparse, [])

    def test_insights_generated_with_sufficient_data(self):
        """Test that insights generate meaningful sentences when sufficient data is present."""
        now = datetime(2026, 10, 12, 12, 0, 0)
        
        # 1. Activity Data (20 rows across multiple days)
        act_rows = []
        for i in range(25):
            t = now - timedelta(days=i % 4, hours=i % 5)
            act_rows.append({
                'timestamp': t.strftime('%Y-%m-%d %H:%M:%S'),
                'keys_per_min': 120 + (i % 20),
                'mouse_events_per_min': 30 + (i % 10),
                'idle_seconds': 10.0 if i % 2 == 0 else 200.0,
                'active_process_name': 'code.exe'
            })
        df_act = pd.DataFrame(act_rows)

        # 2. Energy Data (6 rows)
        en_rows = []
        for i in range(6):
            t = now - timedelta(days=i % 2, hours=i * 2)
            en_rows.append({
                'timestamp': t.strftime('%Y-%m-%d %H:%M:%S'),
                'energy_level': 4 if i % 2 == 0 else 2
            })
        df_en = pd.DataFrame(en_rows)

        # 3. Nudge Data (8 rows across 2 categories)
        nudge_rows = []
        for i in range(8):
            t = now - timedelta(hours=i)
            n_type = 'water_reminder' if i % 2 == 0 else 'posture_check'
            act = 'acted' if i % 2 == 0 else 'dismissed'
            nudge_rows.append({
                'timestamp': t.strftime('%Y-%m-%d %H:%M:%S'),
                'nudge_type': n_type,
                'action': act
            })
        df_nudges = pd.DataFrame(nudge_rows)

        # 4. Decisions (6 rows)
        dec_rows = []
        for i in range(6):
            dec_rows.append({
                'decision': 'delayed' if i % 2 == 0 else 'fired',
                'metadata': '{"source": "model_based"}'
            })
        df_dec = pd.DataFrame(dec_rows)

        insights = generate_insights(
            df_activity=df_act,
            df_energy=df_en,
            df_nudges=df_nudges,
            df_decisions=df_dec,
            avatar_name='Mochi',
            tone='chill'
        )

        self.assertGreater(len(insights), 0)
        self.assertLessEqual(len(insights), 5)
        titles = [ins['title'] for ins in insights]
        self.assertTrue(any('Focus' in t or 'Rhythm' in t or 'Nudge' in t for t in titles))
        # Ensure avatar name is present in sentences
        self.assertTrue(any('Mochi' in ins['text'] for ins in insights))

if __name__ == '__main__':
    unittest.main()
