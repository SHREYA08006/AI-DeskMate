import os
import sys
import json
import sqlite3
import argparse
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List
import pandas as pd

from .features import (
    extract_window_features,
    time_based_train_test_split,
    DEFAULT_WINDOW_MINUTES,
    MAX_LABEL_DISTANCE_MINUTES,
    ENERGY_TO_FATIGUE_MAP
)
from ..paths import get_db_path, get_user_data_dir

def prepare_dataset(
    db_path: Optional[str] = None,
    output_dir: Optional[str] = None,
    window_minutes: int = DEFAULT_WINDOW_MINUTES,
    max_label_dist_min: float = MAX_LABEL_DISTANCE_MINUTES,
    test_ratio: float = 0.2
):
    db_path = db_path or get_db_path()
    output_dir = output_dir or str(get_user_data_dir())
    os.makedirs(output_dir, exist_ok=True)

    print("==========================================================")
    print("   AI DESKMATE -- ML DATASET PREPARATION PIPELINE")
    print("==========================================================")
    print(f"Database: {db_path}")
    print(f"Output Directory: {output_dir}")
    print(f"Window Size: {window_minutes} minutes | Max Label Match: +/-{max_label_dist_min} min\n")

    if not os.path.exists(db_path):
        print(f"Warning: Database file not found at {db_path}.")
        print("Creating empty dataset files...")
        _export_empty_dataset(output_dir)
        return

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        df_activity = pd.read_sql_query("SELECT * FROM activity_log ORDER BY timestamp ASC", conn)
        df_energy = pd.read_sql_query("SELECT * FROM energy_log ORDER BY timestamp ASC", conn)
        try:
            df_decisions = pd.read_sql_query("SELECT * FROM nudge_decision_log ORDER BY timestamp ASC", conn)
        except Exception:
            df_decisions = pd.DataFrame()
    finally:
        conn.close()

    print(f"Loaded Raw Records:")
    print(f"  * Activity log rows: {len(df_activity)}")
    print(f"  * Energy check-in rows: {len(df_energy)}")
    print(f"  * Nudge decisions: {len(df_decisions)}\n")

    if df_activity.empty or df_energy.empty:
        print("Note: Insufficient data in activity_log or energy_log to form labeled pairs.")
        print("Exporting base templates...")
        _export_empty_dataset(output_dir)
        return

    # Extract window features & label matching
    df_features, stats = extract_window_features(
        df_activity=df_activity,
        df_energy=df_energy,
        df_decisions=df_decisions,
        window_minutes=window_minutes,
        max_label_dist_min=max_label_dist_min
    )

    print("----------------------------------------------------------")
    print("1. Windowing & Feature Extraction Results:")
    print(f"  * Total 10-min windows generated: {stats['total_windows_generated']}")
    print(f"  * Windows with active input:      {stats['windows_with_activity']}")
    print(f"  * Labeled windows (energy <=15m): {stats['labeled_windows']}")
    print(f"  * Dropped (unlabeled/no checkin): {stats['dropped_unlabeled']}")
    print(f"  * Dropped (invalid data quality): {stats['dropped_invalid_quality']}")

    # Time-based train/test split
    train_df, test_df = time_based_train_test_split(df_features, test_ratio=test_ratio)

    train_path = os.path.join(output_dir, 'training_data.csv')
    test_path = os.path.join(output_dir, 'test_data.csv')
    summary_path = os.path.join(output_dir, 'dataset_summary.json')

    train_df.to_csv(train_path, index=False)
    test_df.to_csv(test_path, index=False)

    train_class_counts = train_df['fatigue_label'].value_counts().to_dict() if not train_df.empty else {}
    test_class_counts = test_df['fatigue_label'].value_counts().to_dict() if not test_df.empty else {}

    summary = {
        'generated_at': datetime.now().isoformat(),
        'window_minutes': window_minutes,
        'max_label_distance_minutes': max_label_dist_min,
        'fatigue_mapping': ENERGY_TO_FATIGUE_MAP,
        'stats': {
            'total_windows': stats['total_windows_generated'],
            'active_windows': stats['windows_with_activity'],
            'labeled_windows': stats['labeled_windows'],
            'dropped_unlabeled': stats['dropped_unlabeled'],
            'dropped_invalid': stats['dropped_invalid_quality'],
            'train_samples': len(train_df),
            'test_samples': len(test_df),
            'train_class_distribution': train_class_counts,
            'test_class_distribution': test_class_counts,
            'date_range_start': df_features['window_start'].min() if not df_features.empty else None,
            'date_range_end': df_features['window_end'].max() if not df_features.empty else None
        },
        'features': [
            'hour_of_day',
            'day_of_week',
            'avg_keys_per_min',
            'avg_mouse_events_per_min',
            'avg_idle_seconds',
            'time_since_last_break_min',
            'continuous_active_min',
            'app_switch_frequency',
            'is_in_flow_ratio'
        ],
        'targets': ['fatigue_label', 'fatigue_class', 'nearest_energy_level']
    }

    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=4)

    print("\n----------------------------------------------------------")
    print("2. Train / Test Dataset Split & Class Distribution:")
    print(f"  * Training samples: {len(train_df)} | Class balance: {train_class_counts}")
    print(f"  * Testing samples:  {len(test_df)}  | Class balance: {test_class_counts}")
    print("\n----------------------------------------------------------")
    print("3. Export Artifacts Created:")
    print(f"  [OK] {train_path}")
    print(f"  [OK] {test_path}")
    print(f"  [OK] {summary_path}")
    print("==========================================================")

def _export_empty_dataset(output_dir: str):
    cols = [
        'window_start', 'window_end', 'hour_of_day', 'day_of_week',
        'avg_keys_per_min', 'avg_mouse_events_per_min', 'avg_idle_seconds',
        'time_since_last_break_min', 'continuous_active_min',
        'app_switch_frequency', 'is_in_flow_ratio',
        'nearest_energy_level', 'nearest_energy_diff_min',
        'fatigue_label', 'fatigue_class'
    ]
    empty_df = pd.DataFrame(columns=cols)
    empty_df.to_csv(os.path.join(output_dir, 'training_data.csv'), index=False)
    empty_df.to_csv(os.path.join(output_dir, 'test_data.csv'), index=False)

    summary = {
        'generated_at': datetime.now().isoformat(),
        'note': 'Template dataset. No labeled pairs available yet.',
        'stats': {
            'total_windows': 0,
            'labeled_windows': 0,
            'train_samples': 0,
            'test_samples': 0
        },
        'columns': cols
    }
    with open(os.path.join(output_dir, 'dataset_summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=4)

prepare_dataset_pipeline = prepare_dataset

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="AI DeskMate -- Prepare Dataset")
    parser.add_argument("--db", type=str, default=None, help="Path to SQLite database")
    parser.add_argument("--out", type=str, default=None, help="Output directory for CSVs")
    parser.add_argument("--window", type=int, default=10, help="Window size in minutes")
    parser.add_argument("--match-min", type=float, default=15.0, help="Max distance for energy label in minutes")
    parser.add_argument("--test-ratio", type=float, default=0.2, help="Test set ratio (time-based)")
    args = parser.parse_args()

    prepare_dataset(
        db_path=args.db,
        output_dir=args.out,
        window_minutes=args.window,
        max_label_dist_min=args.match_min,
        test_ratio=args.test_ratio
    )
