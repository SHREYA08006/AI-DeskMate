import time
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass, field

from ..db.database import DatabaseManager
from ..settings.config_manager import ConfigManager
from ..ml.predictor import FatiguePredictor, FatiguePrediction
from ..paths import get_db_path
from .adaptive_learning import AdaptiveFrequencyEngine

@dataclass
class NudgeDecision:
    nudge_type: str
    should_fire: bool
    decision: str  # 'fired', 'delayed', 'suppressed', 'not_due'
    reason: str    # 'fired', 'in_flow_delayed', 'idle_suppressed', 'dnd_active', 'snoozed', 'cooldown_active', 'not_due_yet', 'model_low_confidence', 'model_unavailable', 'model_not_fatigued', 'ml_disabled'
    source: str = 'rule_based'  # 'rule_based' or 'model_based'
    params: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

class TriggerEngine:
    SUPPORTED_NUDGE_TYPES = [
        'break_reminder',
        'posture_check',
        'eye_rest',
        'water_reminder',
        'energy_checkin',
        'fatigue_predicted'
    ]

    def __init__(self,
                 db_mgr: Optional[DatabaseManager] = None,
                 config_mgr: Optional[ConfigManager] = None,
                 predictor: Optional[FatiguePredictor] = None,
                 adaptive_engine: Optional[AdaptiveFrequencyEngine] = None,
                 demo: bool = False):
        self.db = db_mgr or DatabaseManager.get_instance(db_path=get_db_path(demo=demo))
        self.config_mgr = config_mgr or ConfigManager()
        self.predictor = predictor or FatiguePredictor.get_instance(demo=demo)
        self.adaptive_engine = adaptive_engine or AdaptiveFrequencyEngine.get_instance(db_mgr=self.db, config_mgr=self.config_mgr)
        self.demo = demo

        self.last_trigger_times: Dict[str, datetime] = {}
        self.cooldown_minutes = 10.0
        self.app_start_time = datetime.now()

    def is_in_mute_window(self, now_dt: Optional[datetime] = None) -> bool:
        if not self.config_mgr.get('mute_hours_enabled', False):
            return False

        now_dt = now_dt or datetime.now()
        now_time = now_dt.time()

        start_str = self.config_mgr.get('mute_hours_start', '22:00')
        end_str = self.config_mgr.get('mute_hours_end', '08:00')

        try:
            start_t = datetime.strptime(start_str, '%H:%M').time()
            end_t = datetime.strptime(end_str, '%H:%M').time()
        except Exception:
            return False

        if start_t <= end_t:
            return start_t <= now_time <= end_t
        else:
            return now_time >= start_t or now_time <= end_t

    def is_user_in_flow(self,
                        activity_state: Optional[Dict[str, Any]] = None,
                        now_dt: Optional[datetime] = None) -> bool:
        if not self.config_mgr.get('flow_detection_enabled', True):
            return False

        threshold = int(self.config_mgr.get('flow_keys_threshold', 120))
        window_minutes = int(self.config_mgr.get('flow_window_minutes', 5))

        # Check explicit in_flow override if supplied in state
        if activity_state and 'is_in_flow' in activity_state:
            return bool(activity_state['is_in_flow'])

        # Query rolling activity log from database
        records = self.db.get_activity_last_minutes(window_minutes)

        if records:
            relevant_records = records[:window_minutes]
            if len(relevant_records) >= 1:
                all_above = all(r.get('keys_per_min', 0) >= threshold for r in relevant_records)
                if activity_state and 'keys_per_min' in activity_state:
                    if activity_state['keys_per_min'] < threshold:
                        return False
                return all_above

        # Fallback to current activity state if DB does not yet have enough records
        if activity_state and 'keys_per_min' in activity_state:
            return activity_state.get('keys_per_min', 0) >= threshold

        return False

    def should_nudge(self,
                     nudge_type: str,
                     activity_state: Dict[str, Any],
                     now_dt: Optional[datetime] = None) -> NudgeDecision:
        now_dt = now_dt or activity_state.get('now_dt') or datetime.now()
        idle_sec = float(activity_state.get('idle_seconds', 0.0))
        idle_suppression_sec = float(self.config_mgr.get('idle_suppression_seconds', 300.0))
        is_snoozed = bool(activity_state.get('is_snoozed', False))
        cont_active = float(activity_state.get('continuous_active_min', 0.0))
        cont_typing = float(activity_state.get('continuous_typing_min', 0.0))

        # 1. Idle Suppression (User away > 5m)
        if idle_sec >= idle_suppression_sec:
            source = 'model_based' if nudge_type == 'fatigue_predicted' else 'rule_based'
            return NudgeDecision(
                nudge_type=nudge_type,
                should_fire=False,
                decision='suppressed',
                reason='idle_suppressed',
                source=source,
                metadata={'idle_seconds': idle_sec}
            )

        # 2. Snooze Check
        if is_snoozed:
            source = 'model_based' if nudge_type == 'fatigue_predicted' else 'rule_based'
            return NudgeDecision(
                nudge_type=nudge_type,
                should_fire=False,
                decision='suppressed',
                reason='snoozed',
                source=source
            )

        # 3. DND / Mute Hours Check
        if self.is_in_mute_window(now_dt):
            source = 'model_based' if nudge_type == 'fatigue_predicted' else 'rule_based'
            return NudgeDecision(
                nudge_type=nudge_type,
                should_fire=False,
                decision='suppressed',
                reason='dnd_active',
                source=source
            )

        # 4. Model-Based Fatigue Nudge Evaluation
        if nudge_type == 'fatigue_predicted':
            if not self.config_mgr.get('enable_ml_fatigue_nudges', True):
                return NudgeDecision(
                    nudge_type='fatigue_predicted',
                    should_fire=False,
                    decision='suppressed',
                    reason='ml_disabled',
                    source='model_based'
                )

            # Check if predictor model is available
            if not self.predictor.is_available():
                return NudgeDecision(
                    nudge_type='fatigue_predicted',
                    should_fire=False,
                    decision='not_due',
                    reason='model_unavailable',
                    source='model_based'
                )

            # Ensure now_dt is in state for feature extraction
            act_state = dict(activity_state)
            act_state['now_dt'] = now_dt
            pred = self.predictor.predict_fatigue(act_state)

            if not pred.available:
                return NudgeDecision(
                    nudge_type='fatigue_predicted',
                    should_fire=False,
                    decision='not_due',
                    reason='model_unavailable',
                    source='model_based'
                )

            if self.demo:
                threshold = 0.5
            else:
                threshold = float(self.config_mgr.get('ml_confidence_threshold', 0.6))
            is_high_fatigue = (pred.predicted_class == 'high_fatigue')
            is_confident = (pred.confidence >= threshold)

            if not is_high_fatigue:
                return NudgeDecision(
                    nudge_type='fatigue_predicted',
                    should_fire=False,
                    decision='not_due',
                    reason='model_not_fatigued',
                    source='model_based',
                    metadata={'prediction': pred.predicted_class, 'confidence': pred.confidence}
                )

            if not is_confident:
                return NudgeDecision(
                    nudge_type='fatigue_predicted',
                    should_fire=False,
                    decision='not_due',
                    reason='model_low_confidence',
                    source='model_based',
                    metadata={'prediction': pred.predicted_class, 'confidence': pred.confidence, 'threshold': threshold}
                )

            # Check cooldown for fatigue predicted nudge
            if not self._can_trigger('fatigue_predicted', now_dt):
                return NudgeDecision(
                    nudge_type='fatigue_predicted',
                    should_fire=False,
                    decision='suppressed',
                    reason='cooldown_active',
                    source='model_based',
                    metadata={'prediction': pred.predicted_class, 'confidence': pred.confidence}
                )

            # Flow state check
            in_flow = self.is_user_in_flow(activity_state, now_dt)
            if in_flow:
                return NudgeDecision(
                    nudge_type='fatigue_predicted',
                    should_fire=False,
                    decision='delayed',
                    reason='in_flow_delayed',
                    source='model_based',
                    params={'confidence': pred.confidence},
                    metadata={'prediction': pred.predicted_class, 'confidence': pred.confidence, 'in_flow': True}
                )

            # Approved to fire via Model!
            return NudgeDecision(
                nudge_type='fatigue_predicted',
                should_fire=True,
                decision='fired',
                reason='fired',
                source='model_based',
                params={'confidence': round(pred.confidence, 2), 'model_type': pred.model_type},
                metadata={
                    'prediction': pred.predicted_class,
                    'confidence': pred.confidence,
                    'probabilities': pred.probabilities,
                    'features_used': pred.features_used
                }
            )

        # 5. Rule-Based Nudge Type Due Evaluation (with Adaptive Frequency Multiplier)
        is_due = False
        params: Dict[str, Any] = {}
        is_hard_override = False
        hour = now_dt.hour

        if nudge_type == 'break_reminder':
            base_interval = float(self.config_mgr.get('break_interval_minutes', 90))
            break_interval = self.adaptive_engine.get_effective_interval(base_interval, hour, now_dt=now_dt)
            if cont_active >= break_interval:
                is_due = True
                is_hard_override = True  # Break reminder interrupts flow state
                params = {'minutes': int(cont_active)}

        elif nudge_type == 'posture_check':
            base_interval = float(self.config_mgr.get('posture_interval_minutes', 45))
            posture_interval = self.adaptive_engine.get_effective_interval(base_interval, hour, now_dt=now_dt)
            if cont_typing >= posture_interval:
                is_due = True
                params = {'minutes': int(cont_typing)}

        elif nudge_type == 'eye_rest':
            base_interval = float(self.config_mgr.get('eye_rest_interval_minutes', 20))
            eye_interval = self.adaptive_engine.get_effective_interval(base_interval, hour, now_dt=now_dt)
            if cont_active >= eye_interval:
                is_due = True
                params = {'minutes': int(cont_active)}

        elif nudge_type == 'water_reminder':
            base_interval = float(self.config_mgr.get('water_interval_minutes', 60))
            water_interval = self.adaptive_engine.get_effective_interval(base_interval, hour, now_dt=now_dt)
            last_water = self.last_trigger_times.get('water_reminder', self.app_start_time)
            diff_min = (now_dt - last_water).total_seconds() / 60.0
            if diff_min >= water_interval:
                is_due = True
                params = {'hours': round(water_interval / 60.0, 1)}

        elif nudge_type == 'energy_checkin':
            base_interval = float(self.config_mgr.get('energy_checkin_interval_minutes', 120))
            energy_interval = self.adaptive_engine.get_effective_interval(base_interval, hour, now_dt=now_dt)
            last_energy = self.last_trigger_times.get('energy_checkin', self.app_start_time)
            diff_min = (now_dt - last_energy).total_seconds() / 60.0
            if diff_min >= energy_interval:
                is_due = True
                params = {'minutes': int(energy_interval)}

        if not is_due:
            return NudgeDecision(
                nudge_type=nudge_type,
                should_fire=False,
                decision='not_due',
                reason='not_due_yet',
                source='rule_based'
            )

        # 6. Cooldown check
        if not self._can_trigger(nudge_type, now_dt):
            return NudgeDecision(
                nudge_type=nudge_type,
                should_fire=False,
                decision='suppressed',
                reason='cooldown_active',
                source='rule_based'
            )

        # 7. Flow State Check
        in_flow = self.is_user_in_flow(activity_state, now_dt)
        if in_flow and not is_hard_override:
            return NudgeDecision(
                nudge_type=nudge_type,
                should_fire=False,
                decision='delayed',
                reason='in_flow_delayed',
                source='rule_based',
                params=params,
                metadata={'in_flow': True}
            )

        # 8. Approved to fire!
        return NudgeDecision(
            nudge_type=nudge_type,
            should_fire=True,
            decision='fired',
            reason='fired',
            source='rule_based',
            params=params,
            metadata={'hard_override': is_hard_override, 'in_flow': in_flow}
        )

    def check_triggers(self,
                        continuous_active_min: float = 0.0,
                        continuous_typing_min: float = 0.0,
                        is_snoozed: bool = False,
                        idle_seconds: float = 0.0,
                        keys_per_min: int = 0,
                        mouse_events_per_min: int = 0,
                        now_dt: Optional[datetime] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        now_dt = now_dt or datetime.now()

        activity_state = {
            'continuous_active_min': continuous_active_min,
            'continuous_typing_min': continuous_typing_min,
            'is_snoozed': is_snoozed,
            'idle_seconds': idle_seconds,
            'keys_per_min': keys_per_min,
            'mouse_events_per_min': mouse_events_per_min,
            'now_dt': now_dt
        }

        fired_trigger: Optional[Tuple[str, Dict[str, Any]]] = None
        in_flow = self.is_user_in_flow(activity_state, now_dt)

        for nudge_type in self.SUPPORTED_NUDGE_TYPES:
            decision = self.should_nudge(nudge_type, activity_state, now_dt)

            # Metadata payload encoding decision source and parameters
            meta_dict = {'source': decision.source, **decision.metadata}
            if decision.params:
                meta_dict['params'] = decision.params

            self.db.log_nudge_decision(
                nudge_type=nudge_type,
                decision=decision.decision,
                reason=decision.reason,
                keys_per_min=keys_per_min,
                mouse_events_per_min=mouse_events_per_min,
                idle_seconds=idle_seconds,
                continuous_active_min=continuous_active_min,
                continuous_typing_min=continuous_typing_min,
                is_in_flow=in_flow,
                metadata=json.dumps(meta_dict)
            )

            if decision.should_fire and fired_trigger is None:
                self._mark_triggered(nudge_type, now_dt)
                fired_trigger = (nudge_type, decision.params)

        return fired_trigger

    def _can_trigger(self, nudge_type: str, now_dt: datetime) -> bool:
        last_t = self.last_trigger_times.get(nudge_type)
        if last_t is None:
            return True
        diff_min = (now_dt - last_t).total_seconds() / 60.0
        return diff_min >= self.cooldown_minutes

    def _mark_triggered(self, nudge_type: str, now_dt: datetime):
        self.last_trigger_times[nudge_type] = now_dt
