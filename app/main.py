import os
import sys
import time
import threading
from datetime import datetime
from typing import Optional
import customtkinter as ctk

if __package__ is None or __package__ == '':
    import os
    import sys
    # Add repo root and bundle dir to sys.path
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from app.utils_logging import get_logger, setup_logging
    from app.instance_manager import InstanceManager
    from app.db.database import DatabaseManager
    from app.settings.config_manager import ConfigManager
    from app.tracker.activity_tracker import ActivityTracker
    from app.nudges.template_engine import TemplateEngine
    from app.nudges.tts_engine import TTSEngine
    from app.nudges.trigger_engine import TriggerEngine
    from app.avatar.avatar_manager import AvatarManager
    from app.ui.onboarding import OnboardingWindow
    from app.ui.settings_window import SettingsWindow
    from app.ui.avatar_overlay import AvatarOverlay
    from app.ui.tray import TrayController
    from app.paths import ensure_user_data_dir, get_db_path, is_first_run
    from app.demo.demo_seeder import DemoManager
    from app.ml.predictor import FatiguePredictor
else:
    from .utils_logging import get_logger, setup_logging
    from .instance_manager import InstanceManager
    from .db.database import DatabaseManager
    from .settings.config_manager import ConfigManager
    from .tracker.activity_tracker import ActivityTracker
    from .nudges.template_engine import TemplateEngine
    from .nudges.tts_engine import TTSEngine
    from .nudges.trigger_engine import TriggerEngine
    from .avatar.avatar_manager import AvatarManager
    from .ui.onboarding import OnboardingWindow
    from .ui.settings_window import SettingsWindow
    from .ui.avatar_overlay import AvatarOverlay
    from .ui.tray import TrayController
    from .paths import ensure_user_data_dir, get_db_path, is_first_run
    from .demo.demo_seeder import DemoManager
    from .ml.predictor import FatiguePredictor

logger = get_logger("main")

class DeskMateApp:
    def __init__(self, is_demo: bool = False):
        ensure_user_data_dir()
        setup_logging()
        self.is_demo = is_demo
        mode_str = "DEMO (Synthetic)" if is_demo else "LIVE"
        logger.info(f"Initializing AI DeskMate application [{mode_str} mode]...")

        self.instance_mgr = InstanceManager()
        is_acquired, unclean_previous = self.instance_mgr.acquire_lock()
        if not is_acquired:
            logger.error("Another instance is already running. Exiting immediately.")
            sys.exit(0)

        self.demo_mgr: Optional[DemoManager] = None
        if self.is_demo:
            db_path = get_db_path(demo=True)
            self.demo_mgr = DemoManager(db_path=db_path)
            self.demo_mgr.seed_if_needed(days=28)
            self.db = DatabaseManager.get_instance(db_path=db_path)
        else:
            self.db = DatabaseManager.get_instance()

        self.config_mgr = ConfigManager()

        if unclean_previous:
            logger.warning("Recovering from unclean previous shutdown...")
            self.db.log_recovery_event("crash_recovery", "Detected unclean shutdown; heartbeat and states restored.")

        self.avatar_mgr = AvatarManager()
        self.avatar_mgr.ensure_assets()
        self.template_engine = TemplateEngine(config_mgr=self.config_mgr)
        self.tts_engine = TTSEngine.get_instance(config_mgr=self.config_mgr)
        self.predictor = FatiguePredictor.get_instance(demo=self.is_demo)
        self.trigger_engine = TriggerEngine(db_mgr=self.db, config_mgr=self.config_mgr, predictor=self.predictor, demo=self.is_demo)
        self.tracker = ActivityTracker(db_manager=self.db, interval_seconds=60)

        self.overlay: Optional[AvatarOverlay] = None
        self.tray: Optional[TrayController] = None
        self.settings_win: Optional[SettingsWindow] = None
        self._running = True

    def start(self):
        try:
            self.tracker.start()

            # Heartbeat thread
            hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True, name="HeartbeatWorker")
            hb_thread.start()

            if not self.is_demo and not self.config_mgr.get('onboarding_completed', False):
                logger.info('First launch detected: Opening Onboarding Wizard...')
                self._show_onboarding()
            else:
                logger.info('Starting AI DeskMate companion...')
                self._start_main_app()
        except Exception as e:
            logger.critical(f"Fatal error during start(): {e}", exc_info=True)
            self.shutdown()

    def _heartbeat_loop(self):
        while self._running:
            try:
                time.sleep(15)
                if not self._running:
                    break
                stats = self.tracker.get_current_stats()
                self.instance_mgr.update_heartbeat(clean_exit=False, extra_state={
                    "continuous_active_min": stats.get("continuous_active_minutes", 0.0),
                    "is_in_grace": stats.get("in_resume_grace_period", False)
                })
            except Exception as e:
                logger.warning(f"Error in heartbeat loop: {e}")

    def _show_onboarding(self):
        try:
            onboarding = OnboardingWindow(config_mgr=self.config_mgr)
            onboarding.mainloop()
        except Exception as e:
            logger.error(f"Error in onboarding window: {e}")
        logger.info('Onboarding completed! Launching companion overlay...')
        self._start_main_app(trigger_welcome=True)

    def _start_main_app(self, trigger_welcome: bool = False):
        try:
            self.overlay = AvatarOverlay(
                config_mgr=self.config_mgr,
                db_mgr=self.db,
                avatar_mgr=self.avatar_mgr,
                on_quit=self.shutdown
            )

            self.tray = TrayController(
                config_mgr=self.config_mgr,
                db_mgr=self.db,
                avatar_mgr=self.avatar_mgr,
                tracker=self.tracker,
                on_check_energy=lambda: self.show_nudge('energy_checkin'),
                on_open_settings=self.open_settings,
                on_test_nudge=self.show_nudge,
                on_trigger_sample_nudge=self._trigger_sample_nudge if self.is_demo else None,
                on_quit=self.shutdown,
                is_demo=self.is_demo
            )

            tray_thread = threading.Thread(target=self.tray.run, daemon=True, name='DeskMateTray')
            tray_thread.start()

            t_sched = threading.Thread(target=self._auto_trigger_loop, daemon=True, name='AutoTriggerLoop')
            t_sched.start()

            # Always show a friendly initial checkin 2.5s after launch to verify avatar is live
            init_delay = 1000 if trigger_welcome else 2500
            self.overlay.after(init_delay, lambda: self.show_nudge('energy_checkin', minutes=0))

            if "--sample-nudge" in sys.argv:
                self.overlay.after(2000, self._trigger_sample_nudge)

            if self.is_demo:
                def _demo_model_nudge():
                    try:
                        demo_state = {
                            'continuous_active_min': 75.0,
                            'time_since_last_break_min': 55.0,
                            'now_dt': datetime.now().replace(hour=15),
                            'keys_per_min': 55,
                            'mouse_events_per_min': 40,
                            'idle_seconds': 15.0,
                            'is_snoozed': False
                        }
                        logger.info("Evaluating demo model-based fatigue check...")
                        dec = self.trigger_engine.should_nudge('fatigue_predicted', demo_state, now_dt=demo_state['now_dt'])
                        logger.info(f"Demo fatigue check decision: should_fire={dec.should_fire}, reason={dec.reason}, source={dec.source}")
                        if dec.should_fire:
                            logger.info(f"Model-based fatigue_predicted nudge fired (confidence={dec.params.get('confidence', 0.85):.2f}, source={dec.source}).")
                            self.db.log_nudge_decision(
                                nudge_type='fatigue_predicted',
                                decision='fired',
                                reason='model_predicted_fatigue',
                                keys_per_min=55,
                                mouse_events_per_min=40,
                                idle_seconds=15.0,
                                continuous_active_min=75.0,
                                continuous_typing_min=40.0,
                                is_in_flow=0,
                                metadata={'source': dec.source, 'confidence': dec.params.get('confidence')}
                            )
                            self.show_nudge('fatigue_predicted', **dec.params)
                    except Exception as e:
                        logger.error(f"Error executing demo model nudge: {e}", exc_info=True)

                self.overlay.after(4000, _demo_model_nudge)

            logger.info('AI DeskMate is live on dock.')
            self.overlay.mainloop()
        except Exception as e:
            logger.critical(f"Critical error in main application loop: {e}", exc_info=True)
            self.shutdown()

    def show_nudge(self, nudge_type: str, **kwargs):
        if self.overlay:
            try:
                if threading.current_thread() is not threading.main_thread():
                    self.overlay.after(0, lambda: self.show_nudge(nudge_type, **kwargs))
                    return
                self.overlay.show_nudge(nudge_type, **kwargs)
            except Exception as e:
                logger.error(f"Error presenting nudge '{nudge_type}': {e}", exc_info=True)

    def open_settings(self):
        if self.overlay:
            self.overlay.after(0, self._open_settings_on_main_thread)

    def _open_settings_on_main_thread(self):
        try:
            if self.settings_win is not None and self.settings_win.winfo_exists():
                self.settings_win.deiconify()
                self.settings_win.lift()
                self.settings_win.focus_force()
                return

            self.settings_win = SettingsWindow(
                config_mgr=self.config_mgr,
                on_settings_changed=self._on_settings_updated
            )
        except Exception as e:
            logger.error(f'Error opening settings: {e}', exc_info=True)

    def _on_settings_updated(self):
        logger.info('Settings saved. Updating live desktop companion...')
        if self.overlay:
            try:
                self.overlay.reload_settings()
            except Exception as e:
                logger.error(f"Error reloading settings in overlay: {e}")

    def _auto_trigger_loop(self):
        while self._running:
            try:
                time.sleep(30)
                if not self._running:
                    break

                # Check post-sleep resume grace period
                stats = self.tracker.get_current_stats()
                if stats.get('in_resume_grace_period', False):
                    logger.debug("Suppressing nudges: tracker in post-sleep resume grace period.")
                    continue

                is_snoozed = self.tray.is_snoozed() if self.tray else False
                cont_active = stats.get('continuous_active_minutes', 0.0)
                cont_typing = stats.get('continuous_typing_minutes', 0.0)
                idle_sec = stats.get('idle_seconds', 0.0)
                keys = stats.get('keys_in_current_interval', 0)
                mouse = stats.get('mouse_in_current_interval', 0)

                # Check activity-based auto triggers (flow-state & idle aware)
                trigger = self.trigger_engine.check_triggers(
                    continuous_active_min=cont_active,
                    continuous_typing_min=cont_typing,
                    is_snoozed=is_snoozed,
                    idle_seconds=idle_sec,
                    keys_per_min=keys,
                    mouse_events_per_min=mouse
                )

                if trigger:
                    nudge_type, params = trigger
                    logger.info(f'Auto-triggered nudge: {nudge_type}')
                    self.show_nudge(nudge_type, **params)
            except Exception as e:
                logger.error(f"Error in auto-trigger evaluation loop: {e}", exc_info=True)
                time.sleep(5.0)

    def _trigger_sample_nudge(self):
        """Cycle through sample nudges in demo mode for recording/demonstration."""
        if self.demo_mgr and self.overlay:
            sample = self.demo_mgr.get_next_sample_nudge()
            logger.info(f"Triggering sample demo nudge: {sample['nudge_type']} (tone: {sample['tone']})")
            self.show_nudge(sample['nudge_type'], tone=sample['tone'])

    def shutdown(self):
        logger.info('Shutting down AI DeskMate cleanly...')
        self._running = False
        try:
            self.tracker.flush_partial_minute()
        except Exception:
            pass
        self.tracker.stop()
        if self.tray:
            self.tray.stop()
        if self.overlay:
            try:
                self.overlay.destroy()
            except Exception:
                pass
        self.instance_mgr.release_lock()
        sys.exit(0)

def main():
    is_companion = "--companion" in sys.argv or "--avatar" in sys.argv or "--avatar-only" in sys.argv

    # If --companion or --avatar is requested, start the desktop companion overlay
    if is_companion:
        is_demo = "--demo" in sys.argv
        app = DeskMateApp(is_demo=is_demo)
        app.start()
        return

    # By default, open the Analytics Dashboard & Command Center at http://localhost:8501
    if __package__ is None or __package__ == '':
        from app.dashboard.launcher import main as launcher_main
    else:
        from .dashboard.launcher import main as launcher_main
    launcher_main()

if __name__ == '__main__':
    main()
