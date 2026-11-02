import os
import json
import unittest
import tempfile
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import joblib
from sklearn.tree import DecisionTreeClassifier

from app.db.database import DatabaseManager
from app.settings.config_manager import ConfigManager
from app.ml.predictor import FatiguePredictor, FatiguePrediction, FEATURE_COLUMNS, CLASS_LABELS
from app.nudges.adaptive_learning import AdaptiveFrequencyEngine
from app.nudges.trigger_engine import TriggerEngine, NudgeDecision

class TestPhase7AdaptiveAndPredictiveEngine(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, 'test_deskmate.db')
        self.config_path = os.path.join(self.temp_dir, 'config.json')
        self.model_path = os.path.join(self.temp_dir, 'fatigue_model.joblib')
        self.meta_path = os.path.join(self.temp_dir, 'model_metadata.json')

        self.db = DatabaseManager(self.db_path)
        self.config_mgr = ConfigManager(self.config_path)

        # Create synthetic trained model
        np.random.seed(42)
        X = np.random.rand(20, len(FEATURE_COLUMNS))
        X_df = pd.DataFrame(X, columns=FEATURE_COLUMNS)
        y = ['high_fatigue' if i % 2 == 0 else 'low_fatigue' for i in range(20)]
        model = DecisionTreeClassifier(max_depth=3)
        model.fit(X_df, y)

        joblib.dump(model, self.model_path)
        with open(self.meta_path, 'w', encoding='utf-8') as f:
            json.dump({
                'selected_model_type': 'decision_tree',
                'feature_columns': FEATURE_COLUMNS,
                'class_labels': CLASS_LABELS
            }, f)

        self.predictor = FatiguePredictor(model_path=self.model_path, metadata_path=self.meta_path)
        self.adaptive_engine = AdaptiveFrequencyEngine(db_mgr=self.db, config_mgr=self.config_mgr)
        self.trigger_engine = TriggerEngine(
            db_mgr=self.db,
            config_mgr=self.config_mgr,
            predictor=self.predictor,
            adaptive_engine=self.adaptive_engine
        )

    def test_predict_fatigue_present_vs_missing_model(self):
        """Test predict_fatigue with present vs missing model file."""
        # 1. Present Model
        self.assertTrue(self.predictor.is_available())
        state = {
            'continuous_active_min': 75.0,
            'keys_per_min': 100,
            'mouse_events_per_min': 30,
            'idle_seconds': 5.0,
            'now_dt': datetime(2026, 9, 19, 14, 0, 0)
        }
        pred = self.predictor.predict_fatigue(state)
        self.assertTrue(pred.available)
        self.assertIn(pred.predicted_class, CLASS_LABELS)
        self.assertGreaterEqual(pred.confidence, 0.0)
        self.assertEqual(len(pred.features_used), len(FEATURE_COLUMNS))

        # 2. Missing Model
        missing_predictor = FatiguePredictor(
            model_path=os.path.join(self.temp_dir, 'nonexistent.joblib'),
            metadata_path=os.path.join(self.temp_dir, 'nonexistent.json')
        )
        self.assertFalse(missing_predictor.is_available())
        pred_missing = missing_predictor.predict_fatigue(state)
        self.assertFalse(pred_missing.available)
        self.assertIsNone(pred_missing.predicted_class)
        self.assertEqual(pred_missing.confidence, 0.0)

    def test_should_nudge_model_based_fatigue_trigger(self):
        """Test fatigue_predicted nudge fires when high_fatigue is predicted with high confidence."""
        # Create a mock predictor that returns confident high_fatigue
        class MockPredictor:
            def is_available(self):
                return True
            def predict_fatigue(self, state):
                return FatiguePrediction(
                    available=True,
                    predicted_class='high_fatigue',
                    confidence=0.92,
                    probabilities={'high_fatigue': 0.92, 'low_fatigue': 0.08},
                    features_used={},
                    model_type='decision_tree'
                )

        engine = TriggerEngine(
            db_mgr=self.db,
            config_mgr=self.config_mgr,
            predictor=MockPredictor(),
            adaptive_engine=self.adaptive_engine
        )

        state = {
            'continuous_active_min': 50.0,
            'idle_seconds': 10.0,
            'is_snoozed': False,
            'now_dt': datetime(2026, 9, 19, 14, 0, 0)
        }

        decision = engine.should_nudge('fatigue_predicted', state)
        self.assertTrue(decision.should_fire)
        self.assertEqual(decision.decision, 'fired')
        self.assertEqual(decision.source, 'model_based')
        self.assertEqual(decision.reason, 'fired')
        self.assertIn('confidence', decision.params)

    def test_should_nudge_defers_to_rule_based_when_model_unavailable_or_low_confidence(self):
        """Test that low confidence or missing model safely suppresses/defers fatigue nudge without breaking rule-based nudges."""
        # Low confidence mock predictor
        class LowConfPredictor:
            def is_available(self):
                return True
            def predict_fatigue(self, state):
                return FatiguePrediction(
                    available=True,
                    predicted_class='high_fatigue',
                    confidence=0.45,  # Below 0.6 threshold
                    probabilities={'high_fatigue': 0.45, 'low_fatigue': 0.55},
                    features_used={},
                    model_type='decision_tree'
                )

        engine = TriggerEngine(
            db_mgr=self.db,
            config_mgr=self.config_mgr,
            predictor=LowConfPredictor(),
            adaptive_engine=self.adaptive_engine
        )

        state = {
            'continuous_active_min': 95.0,  # Exceeds 90m break interval
            'idle_seconds': 0.0,
            'is_snoozed': False,
            'now_dt': datetime(2026, 9, 19, 15, 0, 0)
        }

        # Model fatigue nudge is not due (low confidence)
        fatigue_dec = engine.should_nudge('fatigue_predicted', state)
        self.assertFalse(fatigue_dec.should_fire)
        self.assertEqual(fatigue_dec.decision, 'not_due')
        self.assertEqual(fatigue_dec.source, 'model_based')

        # Rule-based break reminder still fires properly!
        break_dec = engine.should_nudge('break_reminder', state)
        self.assertTrue(break_dec.should_fire)
        self.assertEqual(break_dec.decision, 'fired')
        self.assertEqual(break_dec.source, 'rule_based')

    def test_adaptive_frequency_multiplier_bounds_and_learning(self):
        """Test adaptive frequency multiplier scales with acceptance history and stays within [0.5, 2.0]."""
        now = datetime(2026, 9, 19, 14, 0, 0)

        # 1. Seed 10 positive (acted) interactions for hour 10:00
        for i in range(10):
            t = (now - timedelta(days=i % 3)).replace(hour=10, minute=15)
            self.db.log_nudge(nudge_type='water_reminder', message='Drink water', action='acted', timestamp=t.strftime('%Y-%m-%d %H:%M:%S'))

        # 2. Seed 10 negative (dismissed) interactions for hour 16:00
        for i in range(10):
            t = (now - timedelta(days=i % 3)).replace(hour=16, minute=20)
            self.db.log_nudge(nudge_type='water_reminder', message='Drink water', action='dismissed', timestamp=t.strftime('%Y-%m-%d %H:%M:%S'))

        # Check multiplier at hour 10 (high acceptance -> multiplier > 1.0, up to 2.0)
        mult_10 = self.adaptive_engine.get_frequency_multiplier(10, now_dt=now)
        self.assertGreater(mult_10, 1.0)
        self.assertLessEqual(mult_10, 2.0)

        # Check effective interval at hour 10 (base 60m -> effective < 60m)
        eff_interval_10 = self.adaptive_engine.get_effective_interval(60, 10, now_dt=now)
        self.assertLess(eff_interval_10, 60.0)
        self.assertGreaterEqual(eff_interval_10, 30.0)

        # Check multiplier at hour 16 (high dismiss -> multiplier < 1.0, down to 0.5)
        mult_16 = self.adaptive_engine.get_frequency_multiplier(16, now_dt=now)
        self.assertLess(mult_16, 1.0)
        self.assertGreaterEqual(mult_16, 0.5)

        # Check effective interval at hour 16 (base 60m -> effective > 60m)
        eff_interval_16 = self.adaptive_engine.get_effective_interval(60, 16, now_dt=now)
        self.assertGreater(eff_interval_16, 60.0)
        self.assertLessEqual(eff_interval_16, 120.0)

    def test_decision_logging_tags_sources_accurately(self):
        """Test that check_triggers logs decision rows tagging rule_based vs model_based."""
        class ConfidentPredictor:
            def is_available(self):
                return True
            def predict_fatigue(self, state):
                return FatiguePrediction(
                    available=True,
                    predicted_class='high_fatigue',
                    confidence=0.88,
                    probabilities={'high_fatigue': 0.88},
                    features_used={},
                    model_type='decision_tree'
                )

        engine = TriggerEngine(
            db_mgr=self.db,
            config_mgr=self.config_mgr,
            predictor=ConfidentPredictor(),
            adaptive_engine=self.adaptive_engine
        )

        now = datetime(2026, 9, 19, 11, 0, 0)
        engine.check_triggers(
            continuous_active_min=10.0,
            continuous_typing_min=5.0,
            idle_seconds=0.0,
            keys_per_min=50,
            mouse_events_per_min=20,
            now_dt=now
        )

        # Inspect database decisions
        decisions = self.db.get_recent_nudge_decisions(20)
        self.assertGreater(len(decisions), 0)

        sources_found = set()
        for d in decisions:
            meta = json.loads(d['metadata']) if d['metadata'] else {}
            if 'source' in meta:
                sources_found.add(meta['source'])

        self.assertIn('rule_based', sources_found)
        self.assertIn('model_based', sources_found)

if __name__ == '__main__':
    unittest.main()
