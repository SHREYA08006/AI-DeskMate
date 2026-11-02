import os
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List, Union
import numpy as np
import pandas as pd
import joblib

from ..paths import get_model_path, get_model_metadata_path

logger = logging.getLogger("deskmate.predictor")

FEATURE_COLUMNS = [
    'hour_of_day',
    'day_of_week',
    'avg_keys_per_min',
    'avg_mouse_events_per_min',
    'avg_idle_seconds',
    'time_since_last_break_min',
    'continuous_active_min',
    'app_switch_frequency',
    'is_in_flow_ratio'
]

CLASS_LABELS = ['low_fatigue', 'medium_fatigue', 'high_fatigue']

@dataclass
class FatiguePrediction:
    available: bool
    predicted_class: Optional[str] = None
    confidence: float = 0.0
    probabilities: Dict[str, float] = field(default_factory=dict)
    features_used: Dict[str, float] = field(default_factory=dict)
    model_type: Optional[str] = None
    error_reason: Optional[str] = None

class FatiguePredictor:
    _instances: Dict[Any, 'FatiguePredictor'] = {}

    def __init__(self, model_path: Optional[str] = None, metadata_path: Optional[str] = None, demo: bool = False):
        self.demo = demo
        self.model_path = model_path or get_model_path(demo=demo)
        self.metadata_path = metadata_path or get_model_metadata_path(demo=demo)
        
        self.model = None
        self.metadata: Dict[str, Any] = {}
        self.feature_columns: List[str] = FEATURE_COLUMNS
        self.class_labels: List[str] = CLASS_LABELS
        self.model_type: Optional[str] = None
        self.status: str = "uninitialized"  # "loaded", "missing", "corrupted", "column_mismatch"

        self.load_model()

    @classmethod
    def get_instance(cls, model_path: Optional[str] = None, metadata_path: Optional[str] = None, demo: bool = False) -> 'FatiguePredictor':
        key = (model_path, metadata_path, demo)
        if key not in cls._instances:
            cls._instances[key] = FatiguePredictor(model_path, metadata_path, demo=demo)
        return cls._instances[key]

    def load_model(self) -> bool:
        """
        Loads model and metadata safely with strict safety validation:
        - Missing file -> status='missing', fallback to rule-based.
        - Unpicklable/corrupted -> status='corrupted', fallback to rule-based.
        - Mismatched feature columns -> status='column_mismatch', fallback to rule-based.
        """
        if not os.path.exists(self.model_path) or not os.path.exists(self.metadata_path):
            self.model = None
            self.metadata = {}
            self.status = "missing"
            logger.info("Fatigue model files not found (fresh install). Falling back to rule-based behavior.")
            return False

        try:
            self.model = joblib.load(self.model_path)
        except Exception as e:
            logger.warning(f"Corrupted or invalid fatigue model joblib binary: {e}. Falling back to rule-based behavior.")
            self.model = None
            self.status = "corrupted"
            return False

        try:
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
        except Exception as e:
            logger.warning(f"Corrupted model metadata JSON: {e}. Falling back to rule-based behavior.")
            self.model = None
            self.status = "corrupted"
            return False

        # Verify feature columns match expectation
        meta_features = self.metadata.get('feature_columns', [])
        if not meta_features or set(meta_features) != set(FEATURE_COLUMNS):
            logger.warning(f"Feature columns in metadata ({meta_features}) do not match expected ({FEATURE_COLUMNS}). Safe fallback.")
            self.model = None
            self.status = "column_mismatch"
            return False

        self.feature_columns = meta_features
        self.class_labels = self.metadata.get('class_labels', CLASS_LABELS)
        self.model_type = self.metadata.get('selected_model_type', 'decision_tree')
        self.status = "loaded"
        logger.info(f"Fatigue model successfully loaded ({self.model_type}).")
        return True

    def is_available(self) -> bool:
        return self.model is not None and self.status == "loaded"

    def extract_features(self, activity_state: Dict[str, Any]) -> Dict[str, float]:
        """Extract standard 9 features from live activity state identically to app.ml.features."""
        now_dt = activity_state.get('now_dt')
        if not isinstance(now_dt, datetime):
            now_dt = datetime.now()

        hour = now_dt.hour
        day_of_week = now_dt.weekday()

        keys_per_min = float(activity_state.get('keys_per_min', 0.0))
        mouse_per_min = float(activity_state.get('mouse_events_per_min', 0.0))
        idle_sec = float(activity_state.get('idle_seconds', 0.0))
        continuous_active = float(activity_state.get('continuous_active_min', 0.0))
        
        # Time since last break
        time_since_break = float(activity_state.get('time_since_last_break_min', continuous_active))
        
        # App switch frequency
        app_switch_freq = float(activity_state.get('app_switch_frequency', 0.0))

        # Flow ratio
        if 'is_in_flow_ratio' in activity_state:
            in_flow_ratio = float(activity_state['is_in_flow_ratio'])
        elif 'is_in_flow' in activity_state:
            in_flow_ratio = 1.0 if activity_state['is_in_flow'] else 0.0
        else:
            in_flow_ratio = 0.0

        return {
            'hour_of_day': float(hour),
            'day_of_week': float(day_of_week),
            'avg_keys_per_min': keys_per_min,
            'avg_mouse_events_per_min': mouse_per_min,
            'avg_idle_seconds': idle_sec,
            'time_since_last_break_min': time_since_break,
            'continuous_active_min': continuous_active,
            'app_switch_frequency': app_switch_freq,
            'is_in_flow_ratio': in_flow_ratio
        }

    def predict_fatigue(self, activity_state: Dict[str, Any]) -> FatiguePrediction:
        """Runs live fatigue inference given current activity state with full error trapping."""
        if not self.is_available():
            return FatiguePrediction(
                available=False,
                predicted_class=None,
                confidence=0.0,
                probabilities={},
                features_used={},
                model_type=None,
                error_reason=self.status
            )

        try:
            feats = self.extract_features(activity_state)
            ordered_cols = [c for c in self.feature_columns if c in feats]
            input_df = pd.DataFrame([feats])[ordered_cols]

            raw_pred = self.model.predict(input_df)[0]
            predicted_class = str(raw_pred)

            probs: Dict[str, float] = {}
            confidence = 1.0

            if hasattr(self.model, "predict_proba"):
                prob_vals = self.model.predict_proba(input_df)[0]
                classes = list(getattr(self.model, "classes_", self.class_labels))
                for cls_name, p in zip(classes, prob_vals):
                    probs[str(cls_name)] = round(float(p), 4)
                
                if predicted_class in probs:
                    confidence = probs[predicted_class]
                else:
                    confidence = float(np.max(prob_vals))
            else:
                probs = {predicted_class: 1.0}
                confidence = 1.0

            return FatiguePrediction(
                available=True,
                predicted_class=predicted_class,
                confidence=round(confidence, 4),
                probabilities=probs,
                features_used=feats,
                model_type=self.model_type
            )
        except Exception as e:
            logger.error(f"Inference error in predict_fatigue: {e}")
            return FatiguePrediction(
                available=False,
                predicted_class=None,
                confidence=0.0,
                probabilities={},
                features_used={},
                model_type=self.model_type,
                error_reason=str(e)
            )

def predict_fatigue(activity_state: Dict[str, Any]) -> FatiguePrediction:
    predictor = FatiguePredictor.get_instance()
    return predictor.predict_fatigue(activity_state)
