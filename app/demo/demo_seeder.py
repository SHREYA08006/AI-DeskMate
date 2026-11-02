"""
app/demo/demo_seeder.py - 4-Week Synthetic Data Generator and Model Bootstrapper for Demo Mode.

Generates realistic activity patterns, circadian energy dips, flow states,
nudge outcomes, and pre-trains a demo fatigue model in isolated demo files.
Never modifies the real deskmate.db.
"""

import os
import json
import random
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from ..paths import (
    get_db_path,
    get_model_path,
    get_model_metadata_path,
    get_dataset_path
)
from ..db.database import DatabaseManager

logger = logging.getLogger("deskmate.demo")

SAMPLE_NUDGE_TYPES = [
    "water_reminder",
    "posture_reminder",
    "eye_rest",
    "break_reminder",
    "fatigue_predicted"
]

SAMPLE_TONES = ["chill", "strict", "cheerful", "sarcastic"]


class DemoManager:
    """Manages synthetic demo database and sample nudge cycling."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or get_db_path(demo=True)
        self.db = DatabaseManager(self.db_path)
        self._sample_index = 0

    def seed_if_needed(self, days: int = 28) -> bool:
        """Seed demo database if it has fewer than 200 activity rows."""
        existing_rows = 0
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM activity_log")
                row = cursor.fetchone()
                if row:
                    existing_rows = row[0]
        except Exception:
            existing_rows = 0

        if existing_rows >= 200:
            logger.info(f"Demo database already seeded ({existing_rows} activity records).")
            return False

        logger.info(f"Seeding demo database with {days} days of realistic synthetic data...")
        self.seed_synthetic_data(days=days)
        self.bootstrap_demo_model()
        return True

    def seed_synthetic_data(self, days: int = 28):
        """Populate activity_log, energy_log, nudge_log, nudge_decision_log."""
        total_minutes = days * 24 * 60
        end_time = datetime.now().replace(second=0, microsecond=0)
        start_time = end_time - timedelta(minutes=total_minutes)

        apps = [
            ("Visual Studio Code", "ai-deskmate - main.py"),
            ("Google Chrome", "Stack Overflow - Python questions"),
            ("Slack", "Team Workspace #general"),
            ("Terminal", "PowerShell 7.4"),
            ("Notion", "Sprint Architecture Notes")
        ]

        continuous_active_min = 0.0

        random.seed(42)  # Deterministic realistic pattern

        activity_batch = []
        energy_batch = []
        nudge_batch = []
        decision_batch = []

        for minute_idx in range(total_minutes):
            current = start_time + timedelta(minutes=minute_idx)
            weekday = current.weekday()  # 0=Mon, 6=Sun
            hour = current.hour
            minute = current.minute

            # Work hours: Mon-Fri 09:00 - 18:00, occasional light weekend work
            is_workday = weekday < 5
            is_work_hour = 9 <= hour < 18
            is_lunch = (hour == 12 and minute >= 30) or (hour == 13 and minute < 30)
            is_night = (hour >= 23 or hour < 7)

            # Base probability of being active this minute
            if is_night:
                is_active = False
            elif is_workday:
                if is_lunch:
                    is_active = random.random() < 0.15
                elif is_work_hour:
                    is_active = random.random() < 0.88
                elif hour in (8, 18, 19):
                    is_active = random.random() < 0.35
                else:
                    is_active = False
            else:
                # Weekend: sporadic 1-2 hour sessions
                if 14 <= hour < 17:
                    is_active = random.random() < 0.40
                elif 10 <= hour < 22:
                    is_active = random.random() < 0.15
                else:
                    is_active = False

            if is_active:
                continuous_active_min += 1.0
                
                # Flow period simulation: Mon/Wed/Thu mornings have sustained high typing
                is_flow_session = (weekday in (0, 2, 3)) and (10 <= hour < 11) and (minute < 40)
                
                if is_flow_session:
                    keys = random.randint(140, 210)
                    mouse = random.randint(30, 70)
                    idle = random.uniform(0.0, 5.0)
                elif 14 <= hour < 16:
                    # Afternoon fatigue dip: slower typing, more idle
                    keys = random.randint(35, 85)
                    mouse = random.randint(40, 95)
                    idle = random.uniform(15.0, 45.0)
                else:
                    keys = random.randint(60, 150)
                    mouse = random.randint(50, 130)
                    idle = random.uniform(2.0, 25.0)

                app_name, win_title = random.choice(apps)
            else:
                # Break / inactive minute (guaranteed idle during night)
                continuous_active_min = 0.0
                keys = 0
                mouse = 0 if is_night else random.randint(0, 3)
                idle = 60.0
                app_name, win_title = "Desktop", ""

            # Log every single minute for realistic uninterrupted time series
            activity_batch.append((
                current.strftime("%Y-%m-%d %H:%M:%S"),
                keys,
                mouse,
                win_title,
                app_name,
                round(idle, 1)
            ))

            # Energy check-ins: 2-3 times per workday (around 10:30, 14:45, 17:15)
            if is_workday and minute == 30:
                if hour == 10:
                    # Morning: alert / energetic (rating 4 or 5)
                    rating = random.choices([4, 5], weights=[0.4, 0.6])[0]
                    energy_batch.append((current.strftime("%Y-%m-%d %H:%M:%S"), rating, "periodic_checkin", None))
                elif hour == 14:
                    # Afternoon dip: tired / sluggish (rating 1 or 2)
                    rating = random.choices([1, 2, 3], weights=[0.5, 0.35, 0.15])[0]
                    energy_batch.append((current.strftime("%Y-%m-%d %H:%M:%S"), rating, "periodic_checkin", None))
                elif hour == 17:
                    # End of day: moderate (rating 2 or 3)
                    rating = random.choices([2, 3, 4], weights=[0.4, 0.45, 0.15])[0]
                    energy_batch.append((current.strftime("%Y-%m-%d %H:%M:%S"), rating, "periodic_checkin", None))

            # Nudge generation: realistic intervals during work hours
            if is_workday and is_active and minute in (15, 45) and hour in (10, 11, 14, 15, 16):
                nudge_type = random.choice([
                    "water_reminder", "posture_reminder", "eye_rest", "break_reminder", "fatigue_predicted"
                ])
                outcome = random.choices(["acted", "dismissed", "snoozed"], weights=[0.65, 0.20, 0.15])[0]

                nudge_batch.append((
                    current.strftime("%Y-%m-%d %H:%M:%S"),
                    nudge_type,
                    f"Demo nudge message for {nudge_type}",
                    outcome
                ))

                # Also log decision
                in_flow = 1 if (is_workday and 10 <= hour < 11 and minute < 40) else 0
                fired = 1
                reason = "interval_elapsed" if nudge_type != "fatigue_predicted" else "model_high_fatigue"
                if in_flow and nudge_type != "break_reminder" and random.random() < 0.6:
                    fired = 0
                    reason = "flow_suppressed"

                decision_batch.append((
                    current.strftime("%Y-%m-%d %H:%M:%S"),
                    nudge_type,
                    "fired" if fired else "suppressed",
                    reason,
                    keys,
                    mouse,
                    round(idle, 1),
                    round(continuous_active_min, 1),
                    0.0,
                    1 if in_flow else 0,
                    json.dumps({"source": "model_based" if nudge_type == "fatigue_predicted" else "rule_based"})
                ))

            current += timedelta(minutes=1)

        # Execute in bulk transactions
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO activity_log (timestamp, keys_per_min, mouse_events_per_min, active_window_title, active_process_name, idle_seconds)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', activity_batch)
            cursor.executemany('''
                INSERT INTO energy_log (timestamp, energy_level, prompt_type, notes)
                VALUES (?, ?, ?, ?)
            ''', energy_batch)
            cursor.executemany('''
                INSERT INTO nudge_log (timestamp, nudge_type, message, action)
                VALUES (?, ?, ?, ?)
            ''', nudge_batch)
            cursor.executemany('''
                INSERT INTO nudge_decision_log (
                    timestamp, nudge_type, decision, reason, keys_per_min, mouse_events_per_min,
                    idle_seconds, continuous_active_min, continuous_typing_min, is_in_flow, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', decision_batch)
            conn.commit()

        # Set settings
        self.db.set_setting("onboarding_completed", "True")
        self.db.set_setting("user_name", "Demo User")
        self.db.set_setting("avatar_name", "Mochi")
        self.db.set_setting("avatar_type", "cat")
        self.db.set_setting("personality_tone", "chill")
        self.db.set_setting("is_demo_database", "True")

        logger.info("Demo database seeding complete.")

    def bootstrap_demo_model(self):
        """Train a lightweight Decision Tree classifier on the seeded demo data."""
        try:
            from ..ml.prepare_dataset import prepare_dataset_pipeline
            from ..ml.train_model import train_and_evaluate
            from ..paths import get_user_data_dir

            user_data = get_user_data_dir()
            train_csv = str(user_data / "demo_training_data.csv")
            test_csv = str(user_data / "demo_test_data.csv")
            summary_json = str(user_data / "demo_dataset_summary.json")

            prepare_dataset_pipeline(
                db_path=self.db_path,
                output_dir=str(user_data),
                window_minutes=10,
                max_label_dist_min=20.0
            )

            raw_train = str(user_data / "training_data.csv")
            raw_test = str(user_data / "test_data.csv")
            raw_summary = str(user_data / "dataset_summary.json")

            # Train classifier while raw CSV files exist
            if os.path.exists(raw_train) and os.path.exists(raw_test):
                train_and_evaluate(
                    data_dir=str(user_data),
                    output_dir=str(user_data),
                    random_state=42
                )

            # Rename generated dataset files to demo_ prefix
            if os.path.exists(raw_train):
                if os.path.exists(train_csv):
                    os.remove(train_csv)
                os.rename(raw_train, train_csv)
            if os.path.exists(raw_test):
                if os.path.exists(test_csv):
                    os.remove(test_csv)
                os.rename(raw_test, test_csv)
            if os.path.exists(raw_summary):
                if os.path.exists(summary_json):
                    os.remove(summary_json)
                os.rename(raw_summary, summary_json)

            # Ensure model files are saved to target demo paths
            raw_model = str(user_data / "fatigue_model.joblib")
            raw_meta = str(user_data / "model_metadata.json")
            target_model = get_model_path(demo=True)
            target_meta = get_model_metadata_path(demo=True)

            if os.path.exists(raw_model):
                if os.path.exists(target_model):
                    os.remove(target_model)
                os.rename(raw_model, target_model)
            if os.path.exists(raw_meta):
                if os.path.exists(target_meta):
                    os.remove(target_meta)
                os.rename(raw_meta, target_meta)

            logger.info("Demo fatigue model successfully bootstrapped.")
        except Exception as e:
            logger.warning(f"Could not bootstrap demo model: {e}")

    def get_next_sample_nudge(self) -> Dict[str, str]:
        """Cycle through sample nudge types and tones for recordings."""
        nudge_type = SAMPLE_NUDGE_TYPES[self._sample_index % len(SAMPLE_NUDGE_TYPES)]
        tone = SAMPLE_TONES[(self._sample_index // len(SAMPLE_NUDGE_TYPES)) % len(SAMPLE_TONES)]
        self._sample_index += 1
        return {"nudge_type": nudge_type, "tone": tone}
