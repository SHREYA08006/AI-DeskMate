import os
import json
import unittest
import tempfile
from datetime import datetime, timedelta
import pandas as pd

from app.db.database import DatabaseManager
from app.ml.features import (
    extract_window_features,
    time_based_train_test_split,
    energy_to_fatigue_label,
    energy_to_fatigue_class,
    ENERGY_TO_FATIGUE_MAP
)
from app.ml.prepare_dataset import prepare_dataset

class TestPhase5DatasetPreparation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_deskmate.db')
        self.output_dir = os.path.join(self.temp_dir, 'output')
        os.makedirs(self.output_dir, exist_ok=True)

        self.db = DatabaseManager(self.db_path)

        # Base anchor time
        self.base_time = datetime(2026, 9, 18, 9, 0, 0)

        # Create 60 minutes of synthetic activity data (6 x 10-min windows)
        for m in range(60):
            t = self.base_time + timedelta(minutes=m)
            self.db.log_activity(
                keys_per_min=100 + (m % 30),
                mouse_events_per_min=20 + (m % 10),
                active_window_title='VSCode',
                active_process_name='code.exe',
                idle_seconds=0.0 if m % 15 != 0 else 65.0,
                timestamp=t.strftime('%Y-%m-%d %H:%M:%S')
            )

    def test_energy_to_fatigue_conversion(self):
        """Test fatigue 3-class cutoff mappings."""
        # 5 and 4 -> low_fatigue (Class 0)
        self.assertEqual(energy_to_fatigue_label(5), 'low_fatigue')
        self.assertEqual(energy_to_fatigue_class(5), 0)
        self.assertEqual(energy_to_fatigue_label(4), 'low_fatigue')
        self.assertEqual(energy_to_fatigue_class(4), 0)

        # 3 -> medium_fatigue (Class 1)
        self.assertEqual(energy_to_fatigue_label(3), 'medium_fatigue')
        self.assertEqual(energy_to_fatigue_class(3), 1)

        # 2 and 1 -> high_fatigue (Class 2)
        self.assertEqual(energy_to_fatigue_label(2), 'high_fatigue')
        self.assertEqual(energy_to_fatigue_class(2), 2)
        self.assertEqual(energy_to_fatigue_label(1), 'high_fatigue')
        self.assertEqual(energy_to_fatigue_class(1), 2)

    def test_window_bucketing_and_features(self):
        """Test 10-minute windowing feature extraction."""
        recent_act = self.db.get_recent_activity(100)
        df_act = pd.DataFrame(recent_act)

        # Seed 1 energy rating at 09:05 (center of window 09:00 - 09:10)
        energy_t = (self.base_time + timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
        self.db.log_energy(energy_level=5, prompt_type='checkin', notes='Alert', timestamp=energy_t)
        df_en = pd.DataFrame(self.db.get_recent_energy(10))

        df_feat, stats = extract_window_features(
            df_activity=df_act,
            df_energy=df_en,
            window_minutes=10,
            max_label_dist_min=15.0
        )

        self.assertFalse(df_feat.empty)
        self.assertGreaterEqual(stats['total_windows_generated'], 5)
        self.assertIn('avg_keys_per_min', df_feat.columns)
        self.assertIn('avg_mouse_events_per_min', df_feat.columns)
        self.assertIn('time_since_last_break_min', df_feat.columns)
        self.assertIn('app_switch_frequency', df_feat.columns)
        self.assertIn('fatigue_label', df_feat.columns)

    def test_label_assignment_within_15_minutes_vs_dropped(self):
        """Test nearest label is assigned only if within 15 minutes of window center."""
        recent_act = self.db.get_recent_activity(100)
        df_act = pd.DataFrame(recent_act)

        t_close = (self.base_time + timedelta(minutes=8)).strftime('%Y-%m-%d %H:%M:%S')
        t_far = (self.base_time + timedelta(minutes=80)).strftime('%Y-%m-%d %H:%M:%S')
        
        self.db.log_energy(energy_level=4, prompt_type='checkin', notes='Good', timestamp=t_close)
        self.db.log_energy(energy_level=1, prompt_type='checkin', notes='Tired', timestamp=t_far)

        df_en = pd.DataFrame(self.db.get_recent_energy(10))

        df_feat, stats = extract_window_features(
            df_activity=df_act,
            df_energy=df_en,
            window_minutes=10,
            max_label_dist_min=15.0
        )

        # Window 0 (09:00 - 09:10) should have fatigue_label == 'low_fatigue'
        w0 = df_feat.iloc[0]
        self.assertEqual(w0['fatigue_label'], 'low_fatigue')
        self.assertEqual(w0['nearest_energy_level'], 4)

        # Windows far away should have None/NaN fatigue_label
        unlabeled = df_feat[df_feat['fatigue_label'].isna()]
        self.assertTrue(len(unlabeled) > 0)
        self.assertGreater(stats['dropped_unlabeled'], 0)

    def test_data_quality_filter_drops_implausible_typing(self):
        """Test that impossible typing rates are caught by the quality filter."""
        # Inject corrupted record with 5000 keys/min
        corrupt_act = pd.DataFrame([{
            'timestamp': (self.base_time + timedelta(minutes=1)).strftime('%Y-%m-%d %H:%M:%S'),
            'keys_per_min': 5000,
            'mouse_events_per_min': 20,
            'idle_seconds': 0.0
        }])
        df_en = pd.DataFrame([{'timestamp': self.base_time.strftime('%Y-%m-%d %H:%M:%S'), 'energy_level': 4}])

        df_feat, stats = extract_window_features(
            df_activity=corrupt_act,
            df_energy=df_en,
            window_minutes=10
        )

        self.assertEqual(stats['dropped_invalid_quality'], 1)
        self.assertIn('implausible_typing_or_mouse_rate', stats['drop_reasons'])

    def test_time_based_train_test_split(self):
        """Test chronological split preventing random shuffle leakage."""
        rows = []
        for i in range(10):
            t = self.base_time + timedelta(minutes=i * 10)
            rows.append({
                'window_start': t.isoformat(),
                'window_end': (t + timedelta(minutes=10)).isoformat(),
                'avg_keys_per_min': 100,
                'fatigue_label': 'low_fatigue' if i < 5 else 'high_fatigue',
                'fatigue_class': 0 if i < 5 else 2
            })
        df_features = pd.DataFrame(rows)

        train_df, test_df = time_based_train_test_split(df_features, test_ratio=0.2)

        # 8 train, 2 test
        self.assertEqual(len(train_df), 8)
        self.assertEqual(len(test_df), 2)

        # Verify strict time ordering: all train timestamps < all test timestamps
        max_train_time = pd.to_datetime(train_df['window_start']).max()
        min_test_time = pd.to_datetime(test_df['window_start']).min()
        self.assertLess(max_train_time, min_test_time)

    def test_prepare_dataset_pipeline_execution(self):
        """Test full CLI pipeline execution and file generation."""
        # Log valid energy checkin aligned with activity window
        energy_t = (self.base_time + timedelta(minutes=15)).strftime('%Y-%m-%d %H:%M:%S')
        self.db.log_energy(energy_level=4, prompt_type='checkin', notes='Good', timestamp=energy_t)

        prepare_dataset(
            db_path=self.db_path,
            output_dir=self.output_dir,
            window_minutes=10,
            max_label_dist_min=15.0,
            test_ratio=0.2
        )

        train_file = os.path.join(self.output_dir, 'training_data.csv')
        test_file = os.path.join(self.output_dir, 'test_data.csv')
        summary_file = os.path.join(self.output_dir, 'dataset_summary.json')

        self.assertTrue(os.path.exists(train_file))
        self.assertTrue(os.path.exists(test_file))
        self.assertTrue(os.path.exists(summary_file))

        with open(summary_file, 'r', encoding='utf-8') as f:
            summary = json.load(f)

        self.assertIn('stats', summary)
        self.assertIn('features', summary)
        self.assertIn('targets', summary)

if __name__ == '__main__':
    unittest.main()
