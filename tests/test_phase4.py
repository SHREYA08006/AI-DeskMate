import os
import unittest
import tempfile
from datetime import datetime, timedelta
import pandas as pd

from app.dashboard.analytics import (
    filter_by_date_range,
    get_daily_screentime_trend,
    get_break_adherence_rate,
    get_energy_rating_trend,
    get_hourly_activity_heatmap,
    get_work_block_aggregations,
    get_flow_vs_nudge_behavior
)

class TestPhase4DashboardAnalytics(unittest.TestCase):
    def setUp(self):
        # Generate sample activity data (2 days)
        now = datetime.now()
        activity_records = []
        for d in range(2):
            day_t = now - timedelta(days=d)
            for h in range(8, 12):  # 4 hours per day
                for m in range(0, 60, 5):  # every 5 minutes
                    t = day_t.replace(hour=h, minute=m, second=0)
                    activity_records.append({
                        'timestamp': t.isoformat(),
                        'keys_per_min': 100 if h != 9 else 160,
                        'mouse_events_per_min': 20,
                        'active_window_title': 'Editor',
                        'active_process_name': 'code.exe',
                        'idle_seconds': 0.0 if m < 50 else 70.0
                    })
        self.df_activity = pd.DataFrame(activity_records)

        # Generate sample nudge log
        nudge_records = [
            {'timestamp': (now - timedelta(hours=5)).isoformat(), 'nudge_type': 'water_reminder', 'action': 'acted'},
            {'timestamp': (now - timedelta(hours=4)).isoformat(), 'nudge_type': 'water_reminder', 'action': 'acted'},
            {'timestamp': (now - timedelta(hours=3)).isoformat(), 'nudge_type': 'posture_check', 'action': 'dismissed'},
            {'timestamp': (now - timedelta(hours=2)).isoformat(), 'nudge_type': 'eye_rest', 'action': 'snoozed'},
            {'timestamp': (now - timedelta(hours=1)).isoformat(), 'nudge_type': 'break_reminder', 'action': 'acted'},
        ]
        self.df_nudges = pd.DataFrame(nudge_records)

        # Generate sample energy log
        energy_records = [
            {'timestamp': (now - timedelta(hours=6)).isoformat(), 'energy_level': 4, 'prompt_type': 'periodic_checkin', 'notes': 'Fresh'},
            {'timestamp': (now - timedelta(hours=4)).isoformat(), 'energy_level': 5, 'prompt_type': 'periodic_checkin', 'notes': 'Focused'},
            {'timestamp': (now - timedelta(hours=2)).isoformat(), 'energy_level': 3, 'prompt_type': 'periodic_checkin', 'notes': 'Tired'},
            {'timestamp': (now - timedelta(hours=1)).isoformat(), 'energy_level': 2, 'prompt_type': 'periodic_checkin', 'notes': 'Fatigued'},
        ]
        self.df_energy = pd.DataFrame(energy_records)

        # Generate sample nudge decision log
        decision_records = [
            {'timestamp': (now - timedelta(hours=5)).isoformat(), 'nudge_type': 'water_reminder', 'decision': 'fired', 'reason': 'fired', 'keys_per_min': 50, 'is_in_flow': 0},
            {'timestamp': (now - timedelta(hours=4)).isoformat(), 'nudge_type': 'water_reminder', 'decision': 'delayed', 'reason': 'in_flow_delayed', 'keys_per_min': 150, 'is_in_flow': 1},
            {'timestamp': (now - timedelta(hours=3)).isoformat(), 'nudge_type': 'posture_check', 'decision': 'delayed', 'reason': 'in_flow_delayed', 'keys_per_min': 160, 'is_in_flow': 1},
            {'timestamp': (now - timedelta(hours=2)).isoformat(), 'nudge_type': 'eye_rest', 'decision': 'suppressed', 'reason': 'idle_suppressed', 'keys_per_min': 0, 'is_in_flow': 0},
            {'timestamp': (now - timedelta(hours=1)).isoformat(), 'nudge_type': 'break_reminder', 'decision': 'fired', 'reason': 'fired', 'keys_per_min': 140, 'is_in_flow': 1},
        ]
        self.df_decisions = pd.DataFrame(decision_records)

    def test_daily_screentime_trend_calculation(self):
        trend_df = get_daily_screentime_trend(self.df_activity)
        self.assertEqual(len(trend_df), 2)
        self.assertIn('date', trend_df.columns)
        self.assertIn('active_minutes', trend_df.columns)
        self.assertIn('active_hours', trend_df.columns)
        self.assertGreater(trend_df['active_minutes'].iloc[0], 0)

    def test_break_adherence_rate_calculation(self):
        res = get_break_adherence_rate(self.df_nudges)
        # 3 acted out of 5 total = 60.0%
        self.assertEqual(res['total_nudges'], 5)
        self.assertEqual(res['acted_count'], 3)
        self.assertEqual(res['snoozed_count'], 1)
        self.assertEqual(res['dismissed_count'], 1)
        self.assertEqual(res['overall_rate'], 60.0)

        by_type = res['by_type']
        self.assertFalse(by_type.empty)
        water_row = by_type[by_type['nudge_type'] == 'water_reminder'].iloc[0]
        self.assertEqual(water_row['total'], 2)
        self.assertEqual(water_row['acted'], 2)
        self.assertEqual(water_row['adherence_pct'], 100.0)

    def test_energy_rating_trend_and_averages(self):
        res = get_energy_rating_trend(self.df_energy)
        self.assertEqual(res['total_ratings'], 4)
        # Mean of 4, 5, 3, 2 = 3.5
        self.assertEqual(res['avg_energy'], 3.5)
        self.assertIn('rolling_avg', res['trend_df'].columns)

    def test_hourly_activity_heatmap_matrix(self):
        heatmap_df = get_hourly_activity_heatmap(self.df_activity)
        # Must be 7 days by 24 hours
        self.assertEqual(heatmap_df.shape, (7, 24))
        self.assertIn('Monday', heatmap_df.index)
        self.assertIn('Sunday', heatmap_df.index)
        self.assertEqual(list(heatmap_df.columns), list(range(24)))

    def test_work_block_aggregations_and_longest_streak(self):
        res = get_work_block_aggregations(self.df_activity, self.df_energy)
        self.assertIn('energy_by_hour', res)
        self.assertIn('busiest_blocks', res)
        self.assertIn('longest_streak_minutes', res)
        self.assertGreater(len(res['busiest_blocks']), 0)
        self.assertGreater(res['longest_streak_minutes'], 0)

    def test_flow_vs_nudge_behavior_breakdown(self):
        res = get_flow_vs_nudge_behavior(self.df_decisions)
        self.assertEqual(res['total_decisions'], 5)
        self.assertEqual(res['fired_count'], 2)
        self.assertEqual(res['delayed_count'], 2)
        self.assertEqual(res['suppressed_count'], 1)
        # Due count = 2 fired + 2 delayed = 4; delayed = 2/4 = 50.0%
        self.assertEqual(res['flow_delay_rate_pct'], 50.0)

    def test_empty_dataframe_graceful_handling(self):
        empty_act = pd.DataFrame()
        empty_nudge = pd.DataFrame()
        empty_energy = pd.DataFrame()
        empty_dec = pd.DataFrame()

        self.assertTrue(get_daily_screentime_trend(empty_act).empty)
        adh = get_break_adherence_rate(empty_nudge)
        self.assertEqual(adh['overall_rate'], 0.0)
        self.assertEqual(adh['total_nudges'], 0)

        en = get_energy_rating_trend(empty_energy)
        self.assertEqual(en['avg_energy'], 0.0)

        heat = get_hourly_activity_heatmap(empty_act)
        self.assertEqual(heat.shape, (7, 24))

        flow = get_flow_vs_nudge_behavior(empty_dec)
        self.assertEqual(flow['total_decisions'], 0)

if __name__ == '__main__':
    unittest.main()
