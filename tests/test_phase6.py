import os
import json
import unittest
import tempfile
import pandas as pd
import numpy as np
import joblib

from app.ml.train_model import (
    train_and_evaluate,
    heuristic_predict_fatigue,
    FEATURE_COLUMNS,
    CLASS_LABELS
)

class TestPhase6ModelTraining(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = os.path.join(self.temp_dir, 'data')
        self.output_dir = os.path.join(self.temp_dir, 'output')
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        np.random.seed(42)
        n_train = 60
        n_test = 20

        def create_synthetic_data(n_samples):
            data = []
            for i in range(n_samples):
                hour = np.random.randint(8, 20)
                continuous = np.random.uniform(5, 120)
                break_time = np.random.uniform(0, 90)
                keys = np.random.uniform(10, 200)
                mouse = np.random.uniform(5, 80)
                idle = np.random.uniform(0, 60)
                in_flow = np.random.uniform(0.0, 1.0)
                app_switches = np.random.uniform(0, 15)
                day_of_week = np.random.randint(0, 7)

                if continuous >= 60 or break_time >= 50 or hour >= 16:
                    label = 'high_fatigue'
                elif continuous >= 30 or hour >= 13:
                    label = 'medium_fatigue'
                else:
                    label = 'low_fatigue'

                data.append({
                    'window_start': f'2026-09-18 0{i%10}:00:00',
                    'window_end': f'2026-09-18 0{i%10}:10:00',
                    'hour_of_day': hour,
                    'day_of_week': day_of_week,
                    'avg_keys_per_min': keys,
                    'avg_mouse_events_per_min': mouse,
                    'avg_idle_seconds': idle,
                    'time_since_last_break_min': break_time,
                    'continuous_active_min': continuous,
                    'app_switch_frequency': app_switches,
                    'is_in_flow_ratio': in_flow,
                    'fatigue_label': label,
                    'fatigue_class': CLASS_LABELS.index(label)
                })
            return pd.DataFrame(data)

        self.train_df = create_synthetic_data(n_train)
        self.test_df = create_synthetic_data(n_test)

        self.train_df.to_csv(os.path.join(self.data_dir, 'training_data.csv'), index=False)
        self.test_df.to_csv(os.path.join(self.data_dir, 'test_data.csv'), index=False)

    def test_heuristic_predict_fatigue(self):
        """Test rule-based fatigue prediction logic."""
        high_row = pd.Series({
            'continuous_active_min': 75.0,
            'time_since_last_break_min': 50.0,
            'hour_of_day': 15,
            'is_in_flow_ratio': 0.1
        })
        self.assertEqual(heuristic_predict_fatigue(high_row), 'high_fatigue')

        med_row = pd.Series({
            'continuous_active_min': 35.0,
            'time_since_last_break_min': 20.0,
            'hour_of_day': 11,
            'is_in_flow_ratio': 0.5
        })
        self.assertEqual(heuristic_predict_fatigue(med_row), 'medium_fatigue')

        low_row = pd.Series({
            'continuous_active_min': 10.0,
            'time_since_last_break_min': 5.0,
            'hour_of_day': 10,
            'is_in_flow_ratio': 0.8
        })
        self.assertEqual(heuristic_predict_fatigue(low_row), 'low_fatigue')

    def test_train_and_evaluate_end_to_end(self):
        """Test end-to-end model training, CV, testing, and artifact generation."""
        metadata = train_and_evaluate(data_dir=self.data_dir, output_dir=self.output_dir)

        self.assertIsNotNone(metadata)
        self.assertIn('selected_model_type', metadata)
        self.assertIn(metadata['selected_model_type'], ['decision_tree', 'logistic_regression'])

        model_path = os.path.join(self.output_dir, 'fatigue_model.joblib')
        meta_path = os.path.join(self.output_dir, 'model_metadata.json')
        report_path = os.path.join(self.output_dir, 'model_evaluation_report.md')

        self.assertTrue(os.path.exists(model_path))
        self.assertTrue(os.path.exists(meta_path))
        self.assertTrue(os.path.exists(report_path))

        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)

        self.assertIn('metrics', meta)
        self.assertIn('accuracy', meta['metrics'])
        self.assertGreaterEqual(meta['metrics']['accuracy'], 0.0)
        self.assertIn('heuristic_baseline', meta)
        self.assertIn('feature_importance_ranking', meta)
        self.assertEqual(len(meta['feature_columns']), len(FEATURE_COLUMNS))

        with open(report_path, 'r', encoding='utf-8') as f:
            report_text = f.read()

        self.assertIn("AI DeskMate", report_text)
        self.assertIn("Model Comparison Summary Table", report_text)
        self.assertIn("Feature Importance", report_text)

    def test_saved_model_inference(self):
        """Test loading saved fatigue_model.joblib and running live inference."""
        train_and_evaluate(data_dir=self.data_dir, output_dir=self.output_dir)

        model_path = os.path.join(self.output_dir, 'fatigue_model.joblib')
        model = joblib.load(model_path)

        sample_input = pd.DataFrame([{
            'hour_of_day': 14,
            'day_of_week': 2,
            'avg_keys_per_min': 120.0,
            'avg_mouse_events_per_min': 45.0,
            'avg_idle_seconds': 5.0,
            'time_since_last_break_min': 55.0,
            'continuous_active_min': 65.0,
            'app_switch_frequency': 4.0,
            'is_in_flow_ratio': 0.1
        }])[FEATURE_COLUMNS]

        prediction = model.predict(sample_input)
        self.assertEqual(len(prediction), 1)
        self.assertIn(prediction[0], CLASS_LABELS)

    def test_missing_data_graceful_handling(self):
        """Test graceful exit if training files are missing."""
        empty_dir = tempfile.mkdtemp()
        result = train_and_evaluate(data_dir=empty_dir, output_dir=empty_dir)
        self.assertEqual(result, {})

if __name__ == '__main__':
    unittest.main()
