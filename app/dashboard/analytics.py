from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple, List
import pandas as pd
import numpy as np

def filter_by_date_range(df: pd.DataFrame,
                         date_range: str = 'all',
                         timestamp_col: str = 'timestamp') -> pd.DataFrame:
    if df.empty or timestamp_col not in df.columns:
        return df

    df = df.copy()
    df[timestamp_col] = pd.to_datetime(df[timestamp_col])
    now = datetime.now()

    if date_range == 'today':
        start_date = pd.Timestamp(now.date())
        return df[df[timestamp_col] >= start_date]
    elif date_range == 'week':
        start_date = pd.Timestamp(now.date() - timedelta(days=7))
        return df[df[timestamp_col] >= start_date]
    elif date_range == 'month':
        start_date = pd.Timestamp(now.date() - timedelta(days=30))
        return df[df[timestamp_col] >= start_date]
    else:  # 'all'
        return df

def get_daily_screentime_trend(df_activity: pd.DataFrame) -> pd.DataFrame:
    if df_activity.empty:
        return pd.DataFrame(columns=['date', 'active_minutes', 'active_hours', 'total_keys', 'total_mouse'])

    df = df_activity.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date

    # Active if idle_seconds < 60 or had keystrokes/mouse events
    df['is_active'] = (df['idle_seconds'] < 60.0) | (df['keys_per_min'] > 0) | (df['mouse_events_per_min'] > 0)

    daily = df.groupby('date').agg(
        active_minutes=('is_active', 'sum'),
        total_keys=('keys_per_min', 'sum'),
        total_mouse=('mouse_events_per_min', 'sum')
    ).reset_index()

    daily['active_hours'] = (daily['active_minutes'] / 60.0).round(2)
    daily = daily.sort_values('date')
    return daily

def get_break_adherence_rate(df_nudges: pd.DataFrame) -> Dict[str, Any]:
    if df_nudges.empty:
        return {
            'overall_rate': 0.0,
            'total_nudges': 0,
            'acted_count': 0,
            'snoozed_count': 0,
            'dismissed_count': 0,
            'by_type': pd.DataFrame(columns=['nudge_type', 'total', 'acted', 'snoozed', 'dismissed', 'adherence_pct'])
        }

    df = df_nudges.copy()
    total_nudges = len(df)
    acted_count = int((df['action'] == 'acted').sum())
    snoozed_count = int((df['action'] == 'snoozed').sum())
    dismissed_count = int((df['action'] == 'dismissed').sum())

    overall_rate = round((acted_count / total_nudges) * 100.0, 1) if total_nudges > 0 else 0.0

    # Group by nudge type
    by_type_list = []
    for n_type, grp in df.groupby('nudge_type'):
        t_tot = len(grp)
        t_act = int((grp['action'] == 'acted').sum())
        t_sno = int((grp['action'] == 'snoozed').sum())
        t_dis = int((grp['action'] == 'dismissed').sum())
        t_rate = round((t_act / t_tot) * 100.0, 1) if t_tot > 0 else 0.0
        by_type_list.append({
            'nudge_type': n_type,
            'total': t_tot,
            'acted': t_act,
            'snoozed': t_sno,
            'dismissed': t_dis,
            'adherence_pct': t_rate
        })

    by_type_df = pd.DataFrame(by_type_list)
    if not by_type_df.empty:
        by_type_df = by_type_df.sort_values('total', ascending=False)

    return {
        'overall_rate': overall_rate,
        'total_nudges': total_nudges,
        'acted_count': acted_count,
        'snoozed_count': snoozed_count,
        'dismissed_count': dismissed_count,
        'by_type': by_type_df
    }

def get_energy_rating_trend(df_energy: pd.DataFrame) -> Dict[str, Any]:
    if df_energy.empty:
        return {
            'trend_df': pd.DataFrame(columns=['timestamp', 'energy_level', 'rolling_avg']),
            'avg_energy': 0.0,
            'total_ratings': 0
        }

    df = df_energy.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    df['rolling_avg'] = df['energy_level'].rolling(window=3, min_periods=1).mean().round(2)

    avg_energy = round(float(df['energy_level'].mean()), 2)
    total_ratings = len(df)

    return {
        'trend_df': df,
        'avg_energy': avg_energy,
        'total_ratings': total_ratings
    }

def get_hourly_activity_heatmap(df_activity: pd.DataFrame) -> pd.DataFrame:
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    hours = list(range(24))

    if df_activity.empty:
        return pd.DataFrame(0, index=days, columns=hours)

    df = df_activity.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['day_name'] = df['timestamp'].dt.day_name()
    df['hour'] = df['timestamp'].dt.hour
    df['activity_score'] = df['keys_per_min'] + df['mouse_events_per_min']

    pivot = df.pivot_table(
        index='day_name',
        columns='hour',
        values='activity_score',
        aggfunc='mean',
        fill_value=0
    )

    # Reindex for consistent 7x24 grid
    pivot = pivot.reindex(index=days, fill_value=0)
    pivot = pivot.reindex(columns=hours, fill_value=0)
    return pivot.round(1)

def get_work_block_aggregations(df_activity: pd.DataFrame, df_energy: pd.DataFrame) -> Dict[str, Any]:
    # 1. Average energy by hour
    energy_by_hour = {}
    if not df_energy.empty:
        df_e = df_energy.copy()
        df_e['timestamp'] = pd.to_datetime(df_e['timestamp'])
        df_e['hour'] = df_e['timestamp'].dt.hour
        avg_series = df_e.groupby('hour')['energy_level'].mean().round(2)
        energy_by_hour = avg_series.to_dict()

    # 2. Busiest work blocks & Longest streak
    busiest_blocks = []
    longest_streak_min = 0

    if not df_activity.empty:
        df_a = df_activity.copy()
        df_a['timestamp'] = pd.to_datetime(df_a['timestamp'])
        df_a['hour'] = df_a['timestamp'].dt.hour
        df_a['total_intensity'] = df_a['keys_per_min'] + df_a['mouse_events_per_min']
        
        hourly_intensity = df_a.groupby('hour')['total_intensity'].mean().reset_index()
        top_hours = hourly_intensity.sort_values('total_intensity', ascending=False).head(3)

        for _, row in top_hours.iterrows():
            h = int(row['hour'])
            busiest_blocks.append({
                'block': f"{h:02d}:00 - {(h+1)%24:02d}:00",
                'hour': h,
                'avg_intensity': round(float(row['total_intensity']), 1)
            })

        # Calculate longest continuous active streak
        df_a['is_active'] = df_a['idle_seconds'] < 60.0
        # Group consecutive True values
        streak_groups = (~df_a['is_active']).cumsum()
        active_streaks = df_a[df_a['is_active']].groupby(streak_groups).size()
        longest_streak_min = int(active_streaks.max()) if not active_streaks.empty else 0

    return {
        'energy_by_hour': energy_by_hour,
        'busiest_blocks': busiest_blocks,
        'longest_streak_minutes': longest_streak_min
    }

def get_flow_vs_nudge_behavior(df_decisions: pd.DataFrame) -> Dict[str, Any]:
    if df_decisions.empty:
        return {
            'total_decisions': 0,
            'fired_count': 0,
            'delayed_count': 0,
            'suppressed_count': 0,
            'not_due_count': 0,
            'flow_delay_rate_pct': 0.0,
            'decision_breakdown': pd.DataFrame(columns=['decision', 'count', 'pct']),
            'reason_breakdown': pd.DataFrame(columns=['reason', 'count'])
        }

    df = df_decisions.copy()
    total_decisions = len(df)
    
    fired_count = int((df['decision'] == 'fired').sum())
    delayed_count = int((df['decision'] == 'delayed').sum())
    suppressed_count = int((df['decision'] == 'suppressed').sum())
    not_due_count = int((df['decision'] == 'not_due').sum())

    # Flow delay rate among due nudges (fired + delayed)
    due_count = fired_count + delayed_count
    flow_delay_rate = round((delayed_count / due_count) * 100.0, 1) if due_count > 0 else 0.0

    dec_counts = df['decision'].value_counts().reset_index()
    dec_counts.columns = ['decision', 'count']
    dec_counts['pct'] = (dec_counts['count'] / total_decisions * 100.0).round(1)

    reason_counts = df['reason'].value_counts().reset_index()
    reason_counts.columns = ['reason', 'count']

    return {
        'total_decisions': total_decisions,
        'fired_count': fired_count,
        'delayed_count': delayed_count,
        'suppressed_count': suppressed_count,
        'not_due_count': not_due_count,
        'flow_delay_rate_pct': flow_delay_rate,
        'decision_breakdown': dec_counts,
        'reason_breakdown': reason_counts
    }

def get_hourly_effectiveness_comparison(df_nudges: pd.DataFrame,
                                        now_dt: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Compares nudge effectiveness / acceptance rate per hour: This Week vs Last Week.
    """
    hours = list(range(24))
    empty_df = pd.DataFrame({
        'hour': hours,
        'this_week_rate': [0.0] * 24,
        'last_week_rate': [0.0] * 24,
        'this_week_total': [0] * 24,
        'last_week_total': [0] * 24
    })

    if df_nudges.empty:
        return {
            'comparison_df': empty_df,
            'avg_this_week': 0.0,
            'avg_last_week': 0.0,
            'rate_delta': 0.0
        }

    df = df_nudges.copy()
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['timestamp'].dt.hour
    df['is_acted'] = (df['action'] == 'acted').astype(int)

    now = now_dt or datetime.now()
    t_this_week_start = pd.Timestamp(now - timedelta(days=7))
    t_last_week_start = pd.Timestamp(now - timedelta(days=14))

    # Split into This Week (0-7d) vs Last Week (7-14d)
    # If historical data span is within 7 days, fallback to split by median or available days
    df_this = df[df['timestamp'] >= t_this_week_start]
    df_last = df[(df['timestamp'] >= t_last_week_start) & (df['timestamp'] < t_this_week_start)]

    # If df_last is completely empty because data is young, split earlier half vs later half
    if df_last.empty and len(df) >= 4:
        min_t = df['timestamp'].min()
        mid_t = min_t + (now - min_t) / 2
        df_last = df[df['timestamp'] < mid_t]
        df_this = df[df['timestamp'] >= mid_t]

    rows = []
    for h in hours:
        # This Week Stats
        sub_this = df_this[df_this['hour'] == h]
        t_this = len(sub_this)
        act_this = int(sub_this['is_acted'].sum())
        rate_this = round((act_this / t_this) * 100.0, 1) if t_this > 0 else 0.0

        # Last Week Stats
        sub_last = df_last[df_last['hour'] == h]
        t_last = len(sub_last)
        act_last = int(sub_last['is_acted'].sum())
        rate_last = round((act_last / t_last) * 100.0, 1) if t_last > 0 else 0.0

        rows.append({
            'hour': h,
            'this_week_rate': rate_this,
            'last_week_rate': rate_last,
            'this_week_total': t_this,
            'last_week_total': t_last
        })

    comp_df = pd.DataFrame(rows)

    tot_this = len(df_this)
    tot_last = len(df_last)
    avg_this = round((df_this['is_acted'].sum() / tot_this) * 100.0, 1) if tot_this > 0 else 0.0
    avg_last = round((df_last['is_acted'].sum() / tot_last) * 100.0, 1) if tot_last > 0 else 0.0
    rate_delta = round(avg_this - avg_last, 1)

    return {
        'comparison_df': comp_df,
        'avg_this_week': avg_this,
        'avg_last_week': avg_last,
        'rate_delta': rate_delta
    }

