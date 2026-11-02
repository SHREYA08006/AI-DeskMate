"""
tests/test_phase9.py - Unit & Integration Test Suite for Phase 9:
Packaging Paths, First Run, Autostart, Demo Mode Isolation, and Version Consistency.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path

from app import paths
from app.system import autostart
from app.demo.demo_seeder import DemoManager, SAMPLE_NUDGE_TYPES, SAMPLE_TONES
from app.db.database import DatabaseManager


class TestPhase9PackagingAndDemo(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.old_env_data_dir = os.environ.get("DESKMATE_DATA_DIR")
        os.environ["DESKMATE_DATA_DIR"] = self.test_dir

    def tearDown(self):
        if self.old_env_data_dir is not None:
            os.environ["DESKMATE_DATA_DIR"] = self.old_env_data_dir
        else:
            os.environ.pop("DESKMATE_DATA_DIR", None)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_paths_source_mode_resolution(self):
        """Verify paths.py resolves correctly in standard source mode."""
        self.assertFalse(paths.is_frozen())
        bundle_dir = paths.get_bundle_dir()
        self.assertTrue((bundle_dir / "VERSION").exists() or (bundle_dir / "app").exists())

        # Test user data paths
        user_dir = paths.get_user_data_dir()
        self.assertEqual(user_dir, Path(self.test_dir).resolve())

        # Ensure directory creates logs
        paths.ensure_user_data_dir()
        self.assertTrue((user_dir / "logs").exists())
        self.assertEqual(paths.get_db_path(), str(user_dir / "deskmate.db"))
        self.assertEqual(paths.get_db_path(demo=True), str(user_dir / "demo.db"))
        self.assertEqual(paths.get_config_path(), str(user_dir / "config.json"))

    def test_paths_simulated_frozen_mode(self):
        """Verify paths.py resolves resource directory using sys._MEIPASS when frozen."""
        fake_meipass = os.path.join(self.test_dir, "fake_meipass")
        os.makedirs(fake_meipass, exist_ok=True)
        with open(os.path.join(fake_meipass, "VERSION"), "w", encoding="utf-8") as f:
            f.write("2.5.0\n")

        with patch.object(sys, 'frozen', True, create=True), \
             patch.object(sys, '_MEIPASS', fake_meipass, create=True):
            self.assertTrue(paths.is_frozen())
            self.assertEqual(paths.get_bundle_dir(), Path(fake_meipass).resolve())
            self.assertEqual(paths.get_version(), "2.5.0")
            # User data directory must still point to user data dir, never inside _MEIPASS
            self.assertEqual(paths.get_user_data_dir(), Path(self.test_dir).resolve())

    def test_version_reading_consistency(self):
        """Verify get_version reads consistently from VERSION file."""
        ver = paths.get_version()
        self.assertIsInstance(ver, str)
        self.assertTrue(len(ver) > 0)
        self.assertIn(".", ver)

    def test_autostart_idempotency_with_mocked_registry(self):
        """Verify autostart enable, disable, and query functions are idempotent."""
        fake_registry = {}

        class FakeKey:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        def mock_open_key(root, subkey, reserved, access):
            return FakeKey()

        def mock_set_value_ex(key, name, reserved, reg_type, val):
            fake_registry[name] = val

        def mock_query_value_ex(key, name):
            if name in fake_registry:
                return (fake_registry[name], 1)
            raise FileNotFoundError("Value not found")

        def mock_delete_value(key, name):
            if name in fake_registry:
                del fake_registry[name]
            else:
                raise FileNotFoundError("Value not found")

        with patch("sys.platform", "win32"), \
             patch("winreg.OpenKey", side_effect=mock_open_key), \
             patch("winreg.SetValueEx", side_effect=mock_set_value_ex), \
             patch("winreg.QueryValueEx", side_effect=mock_query_value_ex), \
             patch("winreg.DeleteValue", side_effect=mock_delete_value):

            # Initial status: disabled
            self.assertFalse(autostart.is_autostart_enabled())

            # Enable autostart
            self.assertTrue(autostart.enable_autostart("C:\\Fake\\AIDeskMate.exe"))
            self.assertTrue(autostart.is_autostart_enabled())
            self.assertEqual(fake_registry.get("AIDeskMate"), "C:\\Fake\\AIDeskMate.exe")

            # Enable again (idempotent update)
            self.assertTrue(autostart.enable_autostart("C:\\Fake\\AIDeskMate_Updated.exe"))
            self.assertEqual(fake_registry.get("AIDeskMate"), "C:\\Fake\\AIDeskMate_Updated.exe")

            # Disable autostart
            self.assertTrue(autostart.disable_autostart())
            self.assertFalse(autostart.is_autostart_enabled())

            # Disable again when already disabled (idempotent)
            self.assertTrue(autostart.disable_autostart())
            self.assertFalse(autostart.is_autostart_enabled())

    def test_demo_mode_database_isolation(self):
        """Verify demo mode writes only to demo.db and leaves deskmate.db pristine."""
        paths.ensure_user_data_dir()
        real_db_path = paths.get_db_path(demo=False)
        demo_db_path = paths.get_db_path(demo=True)

        self.assertNotEqual(real_db_path, demo_db_path)
        self.assertTrue(demo_db_path.endswith("demo.db"))

        # Seed real DB with 1 sample record
        real_db = DatabaseManager(real_db_path)
        real_db.log_activity(
            keys_per_min=50,
            mouse_events_per_min=20,
            active_window_title="Real Work",
            active_process_name="WorkApp",
            idle_seconds=5.0,
            timestamp="2026-10-12 10:00:00"
        )

        # Seed demo DB
        demo_mgr = DemoManager(db_path=demo_db_path)
        demo_mgr.seed_synthetic_data(days=7)

        # Inspect real DB: must still have exactly 1 record
        with real_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM activity_log")
            real_count = cursor.fetchone()[0]
        self.assertEqual(real_count, 1)

        # Inspect demo DB: must have multiple days of synthetic activity
        with demo_mgr.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM activity_log")
            demo_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM energy_log")
            energy_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM nudge_log")
            nudge_count = cursor.fetchone()[0]

        self.assertGreater(demo_count, 100)
        self.assertGreater(energy_count, 5)
        self.assertGreater(nudge_count, 5)

    def test_demo_sample_nudge_cycling(self):
        """Verify DemoManager cycles through all sample nudge types and tones."""
        demo_db_path = paths.get_db_path(demo=True)
        demo_mgr = DemoManager(db_path=demo_db_path)

        types_seen = set()
        tones_seen = set()

        # Cycle through multiple rounds
        for _ in range(len(SAMPLE_NUDGE_TYPES) * len(SAMPLE_TONES)):
            sample = demo_mgr.get_next_sample_nudge()
            types_seen.add(sample["nudge_type"])
            tones_seen.add(sample["tone"])

        self.assertEqual(types_seen, set(SAMPLE_NUDGE_TYPES))
        self.assertEqual(tones_seen, set(SAMPLE_TONES))

    def test_demo_setting_labeled_as_synthetic(self):
        """Verify demo database records is_demo_database setting."""
        demo_db_path = paths.get_db_path(demo=True)
        demo_mgr = DemoManager(db_path=demo_db_path)
        demo_mgr.seed_synthetic_data(days=3)

        val = demo_mgr.db.get_setting("is_demo_database")
        self.assertEqual(val, "True")

    def test_demo_nighttime_rows_are_idle(self):
        """Verify demo seeder's nighttime rows (11 PM to 7 AM) are strictly idle."""
        demo_db_path = paths.get_db_path(demo=True)
        demo_mgr = DemoManager(db_path=demo_db_path)
        demo_mgr.seed_synthetic_data(days=7)

        with demo_mgr.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) FROM activity_log
                WHERE (strftime('%H', timestamp) >= '23' OR strftime('%H', timestamp) < '07')
                AND (keys_per_min > 0 OR mouse_events_per_min > 0 OR idle_seconds < 60.0)
            ''')
            violating_rows = cursor.fetchone()[0]
            self.assertEqual(violating_rows, 0, "Nighttime rows must have 0 keys, 0 mouse, and 60s idle")



if __name__ == "__main__":
    unittest.main()
