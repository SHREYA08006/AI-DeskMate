import math
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import pandas as pd

from ..db.database import DatabaseManager
from ..settings.config_manager import ConfigManager

class AdaptiveFrequencyEngine:
    _instance = None

    def __init__(self,
                 db_mgr: Optional[DatabaseManager] = None,
                 config_mgr: Optional[ConfigManager] = None,
                 min_multiplier: float = 0.5,
                 max_multiplier: float = 2.0):
        self.db = db_mgr or DatabaseManager.get_instance()
        self.config_mgr = config_mgr or ConfigManager()
        self.min_multiplier = min_multiplier
        self.max_multiplier = max_multiplier

    @classmethod
    def get_instance(cls,
                     db_mgr: Optional[DatabaseManager] = None,
                     config_mgr: Optional[ConfigManager] = None) -> 'AdaptiveFrequencyEngine':
        if cls._instance is None:
            cls._instance = AdaptiveFrequencyEngine(db_mgr, config_mgr)
        return cls._instance

    def compute_hourly_acceptance_rates(self,
                                       days_lookback: int = 14,
                                       now_dt: Optional[datetime] = None) -> Dict[int, Dict[str, Any]]:
        """
        Computes weighted moving average of acceptance rate per hour-of-day.
        Recent interactions receive higher exponential decay weights.
        """
        now_dt = now_dt or datetime.now()
        start_dt = now_dt - timedelta(days=days_lookback)

        with self.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, nudge_type, action FROM nudge_log
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
            ''', (start_dt.strftime('%Y-%m-%d %H:%M:%S'),))
            rows = cursor.fetchall()

        if not rows:
            return {h: {'acceptance_rate': 0.5, 'total_weight': 0.0, 'sample_count': 0} for h in range(24)}

        hourly_stats: Dict[int, Dict[str, float]] = {
            h: {'weighted_score': 0.0, 'total_weight': 0.0, 'sample_count': 0} for h in range(24)
        }

        for r in rows:
            try:
                t_str = str(r['timestamp'])
                # Handle possible formats
                t = datetime.strptime(t_str[:19], '%Y-%m-%d %H:%M:%S')
            except Exception:
                continue

            hour = t.hour
            days_ago = max(0.0, (now_dt - t).total_seconds() / 86400.0)
            
            # Exponential decay weight: w = exp(-0.1 * days_ago)
            weight = math.exp(-0.1 * days_ago)

            action = str(r['action']).lower()
            if action == 'acted':
                score = 1.0
            elif action == 'dismissed':
                score = 0.0
            elif action == 'snoozed':
                score = 0.5
            else:
                score = 0.5

            hourly_stats[hour]['weighted_score'] += (score * weight)
            hourly_stats[hour]['total_weight'] += weight
            hourly_stats[hour]['sample_count'] += 1

        result: Dict[int, Dict[str, Any]] = {}
        for h in range(24):
            tot_w = hourly_stats[h]['total_weight']
            count = int(hourly_stats[h]['sample_count'])
            if tot_w > 0:
                acc_rate = hourly_stats[h]['weighted_score'] / tot_w
            else:
                acc_rate = 0.5  # Neutral default
            
            result[h] = {
                'acceptance_rate': round(float(acc_rate), 3),
                'total_weight': round(float(tot_w), 2),
                'sample_count': count
            }

        return result

    def get_frequency_multiplier(self,
                                 hour: int,
                                 now_dt: Optional[datetime] = None,
                                 acceptance_cache: Optional[Dict[int, Dict[str, Any]]] = None) -> float:
        """
        Produces an effective frequency multiplier for the given hour:
        - High acceptance rate (>50%) -> Multiplier > 1.0 (nudges allowed more frequently)
        - High dismiss rate (<50%) -> Multiplier < 1.0 (nudges spaced further apart)
        - Safe bounds: strictly clamped between min_multiplier and max_multiplier.
        """
        # Check settings toggle
        if not self.config_mgr.get('enable_adaptive_frequency', True):
            return 1.0

        min_m = float(self.config_mgr.get('min_frequency_multiplier', self.min_multiplier))
        max_m = float(self.config_mgr.get('max_frequency_multiplier', self.max_multiplier))

        if acceptance_cache is None:
            acceptance_cache = self.compute_hourly_acceptance_rates(now_dt=now_dt)

        stats = acceptance_cache.get(hour, {'acceptance_rate': 0.5, 'sample_count': 0})
        acc_rate = stats['acceptance_rate']
        count = stats['sample_count']

        # If insufficient data (< 2 interactions for this hour), use default 1.0
        if count < 2:
            return 1.0

        if acc_rate >= 0.5:
            # Scale from 1.0 to max_m
            multiplier = 1.0 + (acc_rate - 0.5) * 2.0 * (max_m - 1.0)
        else:
            # Scale from min_m to 1.0
            multiplier = min_m + (acc_rate / 0.5) * (1.0 - min_m)

        # Strictly clamp within safe configurable bounds
        clamped = max(min_m, min(max_m, multiplier))
        return round(float(clamped), 2)

    def get_effective_interval(self,
                               base_interval_minutes: float,
                               hour: int,
                               now_dt: Optional[datetime] = None) -> float:
        """
        Adjusts the time interval in minutes according to the frequency multiplier.
        Higher frequency multiplier -> shorter interval (more frequent nudges).
        """
        multiplier = self.get_frequency_multiplier(hour, now_dt=now_dt)
        if multiplier <= 0:
            multiplier = 1.0
        
        effective_interval = base_interval_minutes / multiplier
        return round(effective_interval, 1)
