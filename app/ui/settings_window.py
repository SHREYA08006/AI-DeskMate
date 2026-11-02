import os
import threading
from typing import Optional, Callable
import customtkinter as ctk

from ..settings.config_manager import ConfigManager, AVATAR_OPTIONS, PERSONALITY_TONES
from ..nudges.tts_engine import TTSEngine
from ..system.autostart import is_autostart_enabled, enable_autostart, disable_autostart

ctk.set_appearance_mode('Dark')
ctk.set_default_color_theme('blue')

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self,
                 config_mgr: Optional[ConfigManager] = None,
                 on_settings_changed: Optional[Callable[[], None]] = None):
        super().__init__()
        self.config_mgr = config_mgr or ConfigManager()
        self.on_settings_changed = on_settings_changed
        self.tts_engine = TTSEngine.get_instance(config_mgr=self.config_mgr)

        self.title('AI DeskMate Settings')
        self.geometry('720x860')
        self.minsize(680, 720)
        self.attributes('-topmost', True)

        # State Variables
        self.avatar_type_var = ctk.StringVar(value=self.config_mgr.get('avatar_type', 'cat'))
        self.tone_var = ctk.StringVar(value=self.config_mgr.get('personality_tone', 'chill'))
        self.user_name_var = ctk.StringVar(value=self.config_mgr.get('user_name', 'Friend'))
        self.avatar_name_var = ctk.StringVar(value=self.config_mgr.get('avatar_name', 'Mochi'))
        
        self.tts_var = ctk.BoolVar(value=self.config_mgr.get('tts_enabled', False))
        self.mute_var = ctk.BoolVar(value=self.config_mgr.get('mute_hours_enabled', False))
        self.mute_start_var = ctk.StringVar(value=self.config_mgr.get('mute_hours_start', '22:00'))
        self.mute_end_var = ctk.StringVar(value=self.config_mgr.get('mute_hours_end', '08:00'))
        self.screen_walk_var = ctk.BoolVar(value=self.config_mgr.get('screen_walk_enabled', True))

        self.water_int_var = ctk.StringVar(value=str(self.config_mgr.get('water_interval_minutes', 60)))
        self.break_int_var = ctk.StringVar(value=str(self.config_mgr.get('break_interval_minutes', 90)))
        self.posture_int_var = ctk.StringVar(value=str(self.config_mgr.get('posture_interval_minutes', 45)))
        self.eye_int_var = ctk.StringVar(value=str(self.config_mgr.get('eye_rest_interval_minutes', 20)))
        self.energy_int_var = ctk.StringVar(value=str(self.config_mgr.get('energy_checkin_interval_minutes', 120)))

        # Flow Detection Variables
        self.flow_enabled_var = ctk.BoolVar(value=self.config_mgr.get('flow_detection_enabled', True))
        self.flow_threshold_var = ctk.StringVar(value=str(self.config_mgr.get('flow_keys_threshold', 120)))
        self.flow_window_var = ctk.StringVar(value=str(self.config_mgr.get('flow_window_minutes', 5)))

        # Machine Learning & Adaptive Frequency Variables
        self.ml_fatigue_var = ctk.BoolVar(value=self.config_mgr.get('enable_ml_fatigue_nudges', True))
        self.adaptive_freq_var = ctk.BoolVar(value=self.config_mgr.get('enable_adaptive_frequency', True))
        self.ml_threshold_var = ctk.StringVar(value=str(self.config_mgr.get('ml_confidence_threshold', 0.6)))

        # System Autostart Variable
        self.autostart_var = ctk.BoolVar(value=is_autostart_enabled() or self.config_mgr.get('launch_on_startup', False))

        self._build_ui()

    def _build_ui(self):
        # Header
        header_frame = ctk.CTkFrame(self, fg_color='transparent')
        header_frame.pack(fill='x', padx=24, pady=(20, 10))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text='AI DeskMate Settings',
            font=ctk.CTkFont(size=22, weight='bold')
        )
        title_lbl.pack(anchor='w')

        sub_lbl = ctk.CTkLabel(
            header_frame,
            text='Customize your desktop companion, voice, flow state rules & notifications.',
            font=ctk.CTkFont(size=12),
            text_color='#94A3B8'
        )
        sub_lbl.pack(anchor='w')

        # Scrollable container
        scroll_frame = ctk.CTkScrollableFrame(self, fg_color='transparent')
        scroll_frame.pack(fill='both', expand=True, padx=20, pady=10)

        # 1. Profile Card
        prof_card = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color='#1E293B', border_width=1, border_color='#334155')
        prof_card.pack(fill='x', pady=10, padx=5)

        ctk.CTkLabel(prof_card, text='👤 Companion & User Profile', font=ctk.CTkFont(size=16, weight='bold')).pack(anchor='w', padx=18, pady=(14, 10))

        names_grid = ctk.CTkFrame(prof_card, fg_color='transparent')
        names_grid.pack(fill='x', padx=18, pady=5)

        # User Name
        u_col = ctk.CTkFrame(names_grid, fg_color='transparent')
        u_col.pack(side='left', fill='x', expand=True, padx=(0, 10))
        ctk.CTkLabel(u_col, text='Your Name', font=ctk.CTkFont(size=12, weight='bold'), text_color='#94A3B8').pack(anchor='w')
        ctk.CTkEntry(u_col, textvariable=self.user_name_var, height=36).pack(fill='x', pady=4)

        # Avatar Name + Randomizer
        a_col = ctk.CTkFrame(names_grid, fg_color='transparent')
        a_col.pack(side='left', fill='x', expand=True, padx=(10, 0))
        ctk.CTkLabel(a_col, text='Avatar Name', font=ctk.CTkFont(size=12, weight='bold'), text_color='#94A3B8').pack(anchor='w')
        
        a_row = ctk.CTkFrame(a_col, fg_color='transparent')
        a_row.pack(fill='x', pady=4)
        ctk.CTkEntry(a_row, textvariable=self.avatar_name_var, height=36).pack(side='left', fill='x', expand=True)
        ctk.CTkButton(a_row, text='🎲', width=36, height=36, command=self._randomize_avatar_name, fg_color='#334155', hover_color='#475569').pack(side='left', padx=(6, 0))

        # Avatar Selection
        ctk.CTkLabel(prof_card, text='Select Companion Avatar', font=ctk.CTkFont(size=12, weight='bold'), text_color='#94A3B8').pack(anchor='w', padx=18, pady=(12, 4))
        av_row = ctk.CTkFrame(prof_card, fg_color='transparent')
        av_row.pack(fill='x', padx=18, pady=(0, 10))

        for opt in AVATAR_OPTIONS:
            rb = ctk.CTkRadioButton(
                av_row,
                text=f"{opt['emoji']} {opt['name']}",
                value=opt['type'],
                variable=self.avatar_type_var
            )
            rb.pack(side='left', padx=(0, 12), pady=4)

        # Tone Selection
        ctk.CTkLabel(prof_card, text='Personality Tone', font=ctk.CTkFont(size=12, weight='bold'), text_color='#94A3B8').pack(anchor='w', padx=18, pady=(10, 4))
        tone_row = ctk.CTkFrame(prof_card, fg_color='transparent')
        tone_row.pack(fill='x', padx=18, pady=(0, 16))

        for tone in PERSONALITY_TONES:
            rb = ctk.CTkRadioButton(
                tone_row,
                text=tone['name'],
                value=tone['id'],
                variable=self.tone_var
            )
            rb.pack(side='left', padx=(0, 12), pady=4)

        walk_sw = ctk.CTkSwitch(
            prof_card,
            text='🚶 Walk Across Screen (Walks to center for breaks, speaks, then walks to opposite side)',
            variable=self.screen_walk_var,
            onvalue=True,
            offvalue=False,
            font=ctk.CTkFont(size=13, weight='bold')
        )
        walk_sw.pack(anchor='w', padx=18, pady=(4, 16))

        # 2. Flow State Detection Card (NEW Phase 3)
        flow_card = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color='#1E293B', border_width=1, border_color='#334155')
        flow_card.pack(fill='x', pady=10, padx=5)

        ctk.CTkLabel(flow_card, text='🌊 Flow State & Focus Awareness', font=ctk.CTkFont(size=16, weight='bold')).pack(anchor='w', padx=18, pady=(14, 6))
        ctk.CTkLabel(flow_card, text='Automatically hold non-critical nudges when you are in deep focus/fast typing.', font=ctk.CTkFont(size=12), text_color='#94A3B8').pack(anchor='w', padx=18, pady=(0, 10))

        flow_sw = ctk.CTkSwitch(
            flow_card,
            text='Enable Flow-State Detection (Delay non-critical nudges during fast typing)',
            variable=self.flow_enabled_var,
            onvalue=True,
            offvalue=False,
            font=ctk.CTkFont(size=13, weight='bold')
        )
        flow_sw.pack(anchor='w', padx=18, pady=8)

        flow_grid = ctk.CTkFrame(flow_card, fg_color='transparent')
        flow_grid.pack(fill='x', padx=18, pady=(8, 16))

        # Flow typing threshold
        thresh_col = ctk.CTkFrame(flow_grid, fg_color='transparent')
        thresh_col.pack(side='left', fill='x', expand=True, padx=(0, 10))
        ctk.CTkLabel(thresh_col, text='Fast Typing Threshold (keys/min)', font=ctk.CTkFont(size=12, weight='bold'), text_color='#94A3B8').pack(anchor='w')
        ctk.CTkEntry(thresh_col, textvariable=self.flow_threshold_var, height=36).pack(fill='x', pady=4)

        # Flow window minutes
        win_col = ctk.CTkFrame(flow_grid, fg_color='transparent')
        win_col.pack(side='left', fill='x', expand=True, padx=(10, 0))
        ctk.CTkLabel(win_col, text='Sustained Focus Window (minutes)', font=ctk.CTkFont(size=12, weight='bold'), text_color='#94A3B8').pack(anchor='w')
        ctk.CTkEntry(win_col, textvariable=self.flow_window_var, height=36).pack(fill='x', pady=4)

        # 3. Voice & Speech Card
        voice_card = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color='#1E293B', border_width=1, border_color='#334155')
        voice_card.pack(fill='x', pady=10, padx=5)

        ctk.CTkLabel(voice_card, text='🔊 Voice & Speech (Offline TTS)', font=ctk.CTkFont(size=16, weight='bold')).pack(anchor='w', padx=18, pady=(14, 8))

        tts_row = ctk.CTkFrame(voice_card, fg_color='transparent')
        tts_row.pack(fill='x', padx=18, pady=(0, 14))

        tts_sw = ctk.CTkSwitch(
            tts_row,
            text='Enable Companion Voice (Speaks nudges out loud)',
            variable=self.tts_var,
            onvalue=True,
            offvalue=False,
            font=ctk.CTkFont(size=13, weight='bold')
        )
        tts_sw.pack(side='left', anchor='w')

        test_tts_btn = ctk.CTkButton(
            tts_row,
            text='▶ Test Voice',
            width=100,
            height=30,
            command=self._test_voice,
            fg_color='#2563EB',
            hover_color='#1D4ED8'
        )
        test_tts_btn.pack(side='right', anchor='e')

        # 4. Nudge Intervals Card
        int_card = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color='#1E293B', border_width=1, border_color='#334155')
        int_card.pack(fill='x', pady=10, padx=5)

        ctk.CTkLabel(int_card, text='⏱️ Activity Trigger Intervals (Minutes)', font=ctk.CTkFont(size=16, weight='bold')).pack(anchor='w', padx=18, pady=(14, 10))

        int_grid = ctk.CTkFrame(int_card, fg_color='transparent')
        int_grid.pack(fill='x', padx=18, pady=(0, 14))

        self._add_int_input(int_grid, '💧 Water Reminder', self.water_int_var, 0, 0)
        self._add_int_input(int_grid, '🚶 Break Reminder', self.break_int_var, 0, 1)
        self._add_int_input(int_grid, '🧘 Posture Check', self.posture_int_var, 1, 0)
        self._add_int_input(int_grid, '👀 Eye Rest (20-20-20)', self.eye_int_var, 1, 1)
        self._add_int_input(int_grid, '⚡ Energy Check-in', self.energy_int_var, 2, 0)

        # 5. Do Not Disturb / Mute Hours Card
        mute_card = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color='#1E293B', border_width=1, border_color='#334155')
        mute_card.pack(fill='x', pady=10, padx=5)

        ctk.CTkLabel(mute_card, text='🌙 Do Not Disturb (Mute Hours)', font=ctk.CTkFont(size=16, weight='bold')).pack(anchor='w', padx=18, pady=(14, 8))

        m_sw = ctk.CTkSwitch(
            mute_card,
            text='Mute all automatic nudges during schedule',
            variable=self.mute_var,
            onvalue=True,
            offvalue=False,
            font=ctk.CTkFont(size=13, weight='bold')
        )
        m_sw.pack(anchor='w', padx=18, pady=(0, 10))

        m_row = ctk.CTkFrame(mute_card, fg_color='transparent')
        m_row.pack(fill='x', padx=18, pady=(0, 16))

        ctk.CTkLabel(m_row, text='Start Time (HH:MM):', font=ctk.CTkFont(size=12), text_color='#94A3B8').pack(side='left', padx=(0, 6))
        ctk.CTkEntry(m_row, textvariable=self.mute_start_var, width=80, height=32).pack(side='left', padx=(0, 20))

        ctk.CTkLabel(m_row, text='End Time (HH:MM):', font=ctk.CTkFont(size=12), text_color='#94A3B8').pack(side='left', padx=(0, 6))
        ctk.CTkEntry(m_row, textvariable=self.mute_end_var, width=80, height=32).pack(side='left')

        # 6. Machine Learning & Adaptive Engine Card
        ml_card = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color='#1E293B', border_width=1, border_color='#334155')
        ml_card.pack(fill='x', pady=10, padx=5)

        ctk.CTkLabel(ml_card, text='🧠 AI Fatigue Model & Adaptive Frequency', font=ctk.CTkFont(size=16, weight='bold')).pack(anchor='w', padx=18, pady=(14, 8))

        ml_sw = ctk.CTkSwitch(
            ml_card,
            text='Enable Model-Driven Fatigue Predictions',
            variable=self.ml_fatigue_var,
            onvalue=True,
            offvalue=False,
            font=ctk.CTkFont(size=13, weight='bold')
        )
        ml_sw.pack(anchor='w', padx=18, pady=(0, 8))

        adapt_sw = ctk.CTkSwitch(
            ml_card,
            text='Enable Hourly Adaptive Nudge Frequency',
            variable=self.adaptive_freq_var,
            onvalue=True,
            offvalue=False,
            font=ctk.CTkFont(size=13, weight='bold')
        )
        adapt_sw.pack(anchor='w', padx=18, pady=(0, 10))

        thresh_row = ctk.CTkFrame(ml_card, fg_color='transparent')
        thresh_row.pack(fill='x', padx=18, pady=(0, 16))

        ctk.CTkLabel(thresh_row, text='Model Confidence Threshold (0.0 - 1.0):', font=ctk.CTkFont(size=12), text_color='#94A3B8').pack(side='left', padx=(0, 10))
        ctk.CTkEntry(thresh_row, textvariable=self.ml_threshold_var, width=70, height=32).pack(side='left')

        # 7. System & Autostart Card
        sys_card = ctk.CTkFrame(scroll_frame, corner_radius=12, fg_color='#1E293B', border_width=1, border_color='#334155')
        sys_card.pack(fill='x', pady=8)

        ctk.CTkLabel(
            sys_card,
            text='⚙️ System & Autostart',
            font=ctk.CTkFont(size=15, weight='bold')
        ).pack(anchor='w', padx=18, pady=(16, 12))

        autostart_sw = ctk.CTkSwitch(
            sys_card,
            text='Launch AI DeskMate automatically when I sign in',
            variable=self.autostart_var,
            onvalue=True,
            offvalue=False,
            font=ctk.CTkFont(size=13, weight='bold')
        )
        autostart_sw.pack(anchor='w', padx=18, pady=(0, 16))

        # Footer Actions
        footer = ctk.CTkFrame(self, fg_color='transparent')
        footer.pack(fill='x', padx=24, pady=16)

        save_btn = ctk.CTkButton(
            footer,
            text='💾 Save Changes',
            font=ctk.CTkFont(size=14, weight='bold'),
            height=42,
            fg_color='#10B981',
            hover_color='#059669',
            command=self._save_settings
        )
        save_btn.pack(side='right', padx=(10, 0))

        cancel_btn = ctk.CTkButton(
            footer,
            text='Cancel',
            font=ctk.CTkFont(size=14),
            height=42,
            fg_color='#334155',
            hover_color='#475569',
            command=self.destroy
        )
        cancel_btn.pack(side='right')

    def _add_int_input(self, parent, label, var, r, c):
        f = ctk.CTkFrame(parent, fg_color='transparent')
        f.grid(row=r, column=c, sticky='ew', padx=8, pady=6)
        parent.grid_columnconfigure(c, weight=1)
        ctk.CTkLabel(f, text=label, font=ctk.CTkFont(size=12, weight='bold'), text_color='#94A3B8').pack(anchor='w')
        ctk.CTkEntry(f, textvariable=var, height=32).pack(fill='x', pady=2)

    def _randomize_avatar_name(self):
        new_name = ConfigManager.get_random_name(self.avatar_type_var.get())
        self.avatar_name_var.set(new_name)

    def _test_voice(self):
        name = self.avatar_name_var.get() or 'DeskMate'
        user = self.user_name_var.get() or 'Friend'
        sample_msg = f"Hello {user}! I am {name}, your AI DeskMate companion."
        self.tts_engine.speak(sample_msg)

    def _save_settings(self):
        def _safe_int(val, default):
            try:
                return int(str(val).strip())
            except (ValueError, TypeError):
                return default

        def _safe_float(val, default):
            try:
                return float(str(val).strip())
            except (ValueError, TypeError):
                return default

        try:
            updates = {
                'avatar_type': self.avatar_type_var.get(),
                'personality_tone': self.tone_var.get(),
                'user_name': self.user_name_var.get().strip() or 'Friend',
                'avatar_name': self.avatar_name_var.get().strip() or 'Mochi',
                'tts_enabled': self.tts_var.get(),
                'mute_hours_enabled': self.mute_var.get(),
                'mute_hours_start': self.mute_start_var.get().strip() or '22:00',
                'mute_hours_end': self.mute_end_var.get().strip() or '08:00',
                'water_interval_minutes': _safe_int(self.water_int_var.get(), 60),
                'break_interval_minutes': _safe_int(self.break_int_var.get(), 90),
                'posture_interval_minutes': _safe_int(self.posture_int_var.get(), 45),
                'eye_rest_interval_minutes': _safe_int(self.eye_int_var.get(), 20),
                'energy_checkin_interval_minutes': _safe_int(self.energy_int_var.get(), 120),
                'flow_detection_enabled': self.flow_enabled_var.get(),
                'flow_keys_threshold': _safe_int(self.flow_threshold_var.get(), 120),
                'flow_window_minutes': _safe_int(self.flow_window_var.get(), 5),
                'enable_ml_fatigue_nudges': self.ml_fatigue_var.get(),
                'enable_adaptive_frequency': self.adaptive_freq_var.get(),
                'ml_confidence_threshold': _safe_float(self.ml_threshold_var.get(), 0.6),
                'launch_on_startup': self.autostart_var.get()
            }

            # Update Windows Run registry key
            if self.autostart_var.get():
                enable_autostart()
            else:
                disable_autostart()

            self.config_mgr.update(updates)
            print('Settings saved successfully.')

            if self.on_settings_changed:
                self.on_settings_changed()

            self.destroy()
        except Exception as e:
            print(f'Error saving settings: {e}')
