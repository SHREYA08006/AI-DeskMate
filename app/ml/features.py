import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

# Configurable constants for dataset preparation
DEFAULT_WINDOW_MINUTES = 10
MAX_LABEL_DISTANCE_MINUTES = 15.0
MAX_PLAUSIBLE_KEYS_PER_MIN = 800
MAX_PLAUSIBLE_MOUSE_PER_MIN = 1000

# Configurable Fatigue Mapping
# Energy ratings: 1 (Very Tired) to 5 (High Energy)
# Fatigue classification: 
#   Energy 4-5 -> low_fatigue (Class 0)
#   Energy 3   -> medium_fatigue (Class 1)
#   Energy 1-2 -> high_fatigue (Class 2)
ENERGY_TO_FATIGUE_MAP = {
    5: 'low_fatigue',
    4: 'low_fatigue',
    3: 'medium_fatigue',
    2: 'high_fatigue',
    1: 'high_fatigue'
}

FATIGUE_CLASS_INDICES = {
    'low_fatigue': 0,
    'medium_fatigue': 1,
    'high_fatigue': 2
}

def energy_to_fatigue_label(energy_rating: int) -> str:
    try:
        r = int(round(energy_rating))
        return ENERGY_TO_FATIGUE_MAP.get(r, 'medium_fatigue')
    except Exception:
        return 'medium_fatigue'

def energy_to_fatigue_class(energy_rating: int) -> int:
    label = energy_to_fatigue_label(energy_rating)
    return FATIGUE_CLASS_INDICES.get(label, 1)

def extract_window_features(
    df_activity: pd.DataFrame,
    df_energy: pd.DataFrame,
    df_decisions: Optional[pd.DataFrame] = None,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
    max_label_dist_min: float = MAX_LABEL_DISTANCE_MINUTES
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    stats = {
        'total_windows_generated': 0,
        'windows_with_activity': 0,
        'labeled_windows': 0,
        'dropped_unlabeled': 0,
        'dropped_invalid_quality': 0,
        'drop_reasons': {}
    }

    if df_activity.empty:
        return pd.DataFrame(), stats

    df_act = df_activity.copy()
    df_act['timestamp'] = pd.to_datetime(df_act['timestamp'])
    df_act = df_act.sort_values('timestamp').reset_index(drop=True)

    df_en = pd.DataFrame()
    if df_energy is not None and not df_energy.empty:
        df_en = df_energy.copy()
        df_en['timestamp'] = pd.to_datetime(df_en['timestamp'])
        df_en = df_en.sort_values('timestamp').reset_index(drop=True)

    df_dec = pd.DataFrame()
    if df_decisions is not None and not df_decisions.empty:
        df_dec = df_decisions.copy()
        df_dec['timestamp'] = pd.to_datetime(df_dec['timestamp'])
        df_dec = df_dec.sort_values('timestamp').reset_index(drop=True)

    # Determine time bounds
    min_time = df_act['timestamp'].min().floor(f'{window_minutes}min')
    max_time = df_act['timestamp'].max().ceil(f'{window_minutes}min')

    if min_time == max_time:
        max_time = min_time + timedelta(minutes=window_minutes)

    window_rows = []
    current_time = min_time
    last_break_time = min_time
    continuous_active_running_min = 0.0

    while current_time < max_time:
        w_start = current_time
        w_end = w_start + timedelta(minutes=window_minutes)
        w_center = w_start + timedelta(minutes=window_minutes / 2.0)
        current_time = w_end

        stats['total_windows_generated'] += 1

        # Activity slice
        act_slice = df_act[(df_act['timestamp'] >= w_start) & (df_act['timestamp'] < w_end)]

        if act_slice.empty:
            stats['dropped_unlabeled'] += 1
            stats['drop_reasons']['no_activity_in_window'] = stats['drop_reasons'].get('no_activity_in_window', 0) + 1
            continue

        stats['windows_with_activity'] += 1

        # Data Quality Check on raw activity
        keys_mean = float(act_slice['keys_per_min'].mean())
        mouse_mean = float(act_slice['mouse_events_per_min'].mean())
        idle_mean = float(act_slice['idle_seconds'].mean()) if 'idle_seconds' in act_slice.columns else 0.0

        if keys_mean < 0 or keys_mean > MAX_PLAUSIBLE_KEYS_PER_MIN or mouse_mean < 0 or mouse_mean > MAX_PLAUSIBLE_MOUSE_PER_MIN:
            stats['dropped_invalid_quality'] += 1
            stats['drop_reasons']['implausible_typing_or_mouse_rate'] = stats['drop_reasons'].get('implausible_typing_or_mouse_rate', 0) + 1
            continue

        # Calculate time since last break & continuous active minutes
        # Check if user had a break in this window (idle_seconds > 180s / 3 min)
        had_break_in_window = (act_slice['idle_seconds'] >= 180.0).any() if 'idle_seconds' in act_slice.columns else False
        if had_break_in_window:
            last_break_time = w_end
            continuous_active_running_min = max(0.0, float(window_minutes - (act_slice['idle_seconds'].max() / 60.0)))
        else:
            continuous_active_running_min += window_minutes

        time_since_last_break = max(0.0, (w_end - last_break_time).total_seconds() / 60.0)

        # App switch frequency within window
        app_switches = 0
        if 'active_process_name' in act_slice.columns and len(act_slice) > 1:
            app_switches = int((act_slice['active_process_name'] != act_slice['active_process_name'].shift()).sum() - 1)
            app_switches = max(0, app_switches)
        elif 'active_window_title' in act_slice.columns and len(act_slice) > 1:
            app_switches = int((act_slice['active_window_title'] != act_slice['active_window_title'].shift()).sum() - 1)
            app_switches = max(0, app_switches)

        # Flow ratio from nudge_decision_log or fast typing
        flow_ratio = 0.0
        if not df_dec.empty:
            dec_slice = df_dec[(df_dec['timestamp'] >= w_start) & (df_dec['timestamp'] < w_end)]
            if not dec_slice.empty and 'is_in_flow' in dec_slice.columns:
                flow_ratio = float(dec_slice['is_in_flow'].mean())
            else:
                flow_ratio = float((act_slice['keys_per_min'] >= 120).mean())
        else:
            flow_ratio = float((act_slice['keys_per_min'] >= 120).mean())

        # Nearest energy rating
        energy_val = np.nan
        label_str = None
        label_class = None
        nearest_time_diff = np.nan

        if not df_en.empty:
            time_diffs = (df_en['timestamp'] - w_center).abs()
            nearest_idx = time_diffs.idxmin()
            nearest_diff_min = time_diffs.loc[nearest_idx].total_seconds() / 60.0

            if nearest_diff_min <= max_label_dist_min:
                energy_val = int(df_en.loc[nearest_idx, 'energy_level'])
                label_str = energy_to_fatigue_label(energy_val)
                label_class = energy_to_fatigue_class(energy_val)
                nearest_time_diff = round(nearest_diff_min, 1)

        window_row = {
            'window_start': w_start.isoformat(),
            'window_end': w_end.isoformat(),
            'hour_of_day': int(w_start.hour),
            'day_of_week': int(w_start.weekday()),
            'avg_keys_per_min': round(keys_mean, 2),
            'avg_mouse_events_per_min': round(mouse_mean, 2),
            'avg_idle_seconds': round(idle_mean, 2),
            'time_since_last_break_min': round(time_since_last_break, 1),
            'continuous_active_min': round(continuous_active_running_min, 1),
            'app_switch_frequency': int(app_switches),
            'is_in_flow_ratio': round(flow_ratio, 2),
            'nearest_energy_level': energy_val if not np.isnan(energy_val) else None,
            'nearest_energy_diff_min': nearest_time_diff if not np.isnan(nearest_time_diff) else None,
            'fatigue_label': label_str,
            'fatigue_class': label_class
        }
        window_rows.append(window_row)

    df_result = pd.DataFrame(window_rows)
    if not df_result.empty:
        stats['labeled_windows'] = int(df_result['fatigue_label'].notna().sum())
        stats['dropped_unlabeled'] += int(df_result['fatigue_label'].isna().sum())

    return df_result, stats

def time_based_train_test_split(
    df_features: pd.DataFrame,
    test_ratio: float = 0.2
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if df_features.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Filter to only labeled records
    df_labeled = df_features[df_features['fatigue_label'].notna()].copy()
    if df_labeled.empty:
        return pd.DataFrame(), pd.DataFrame()

    df_labeled['window_start'] = pd.to_datetime(df_labeled['window_start'])
    df_labeled = df_labeled.sort_values('window_start').reset_index(drop=True)

    n_samples = len(df_labeled)
    if n_samples == 1:
        return df_labeled, df_labeled.copy()

    split_idx = int(np.floor(n_samples * (1.0 - test_ratio)))
    split_idx = max(1, min(split_idx, n_samples - 1))

    train_df = df_labeled.iloc[:split_idx].copy()
    test_df = df_labeled.iloc[split_idx:].copy()

    return train_df, test_df
