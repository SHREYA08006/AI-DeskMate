import os
import sys
import tkinter as tk
from typing import Optional, Callable
import customtkinter as ctk

from ..settings.config_manager import ConfigManager
from ..db.database import DatabaseManager
from ..avatar.avatar_manager import AvatarManager, AVATAR_CONFIGS
from ..avatar.animation_controller import AnimationController
from ..nudges.template_engine import TemplateEngine
from ..nudges.tts_engine import TTSEngine
from ..utils_logging import get_logger

logger = get_logger("overlay")

class AvatarOverlay(ctk.CTk):
    def __init__(self,
                 config_mgr: Optional[ConfigManager] = None,
                 db_mgr: Optional[DatabaseManager] = None,
                 avatar_mgr: Optional[AvatarManager] = None,
                 on_quit: Optional[Callable[[], None]] = None):
        super().__init__()
        self.config_mgr = config_mgr or ConfigManager()
        self.db_mgr = db_mgr or DatabaseManager.get_instance()
        self.avatar_mgr = avatar_mgr or AvatarManager()
        self.template_engine = TemplateEngine(config_mgr=self.config_mgr)
        self.tts_engine = TTSEngine.get_instance(config_mgr=self.config_mgr)
        self.on_quit = on_quit

        self.avatar_type = self.config_mgr.get('avatar_type', 'cat')
        self.user_name = self.config_mgr.get('user_name', 'Friend')
        self.avatar_name = self.config_mgr.get('avatar_name', 'Mochi')
        self.tone = self.config_mgr.get('personality_tone', 'chill')

        self.is_expanded = False
        self.current_nudge_type = None
        self.current_message = ''

        self._configure_window()
        self._build_ui()
        self._apply_layout_collapsed()

    def _configure_window(self):
        self.title(f'{self.avatar_name}')
        self.overrideredirect(True)
        self.attributes('-topmost', True)

        # Multi-monitor & DPI safety: enable non-activating window on Windows to avoid stealing keyboard focus
        if sys.platform == 'win32':
            try:
                import ctypes
                hwnd = self.winfo_id()
                GWL_EXSTYLE = -20
                WS_EX_NOACTIVATE = 0x08000000
                current_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, current_style | WS_EX_NOACTIVATE)
            except Exception as e:
                logger.debug(f"Could not apply WS_EX_NOACTIVATE: {e}")

        self.collapsed_w = 114
        self.collapsed_h = 126
        self.expanded_w = 410
        self.expanded_h = 230

        self._set_collapsed_geometry()

    def _get_safe_screen_bounds(self) -> tuple:
        """Returns safe screen width and height handling multi-monitor and DPI scaling."""
        try:
            screen_w = self.winfo_screenwidth()
            screen_h = self.winfo_screenheight()
            return max(800, screen_w), max(600, screen_h)
        except Exception:
            return 1920, 1080

    def _set_collapsed_geometry(self):
        screen_w, screen_h = self._get_safe_screen_bounds()
        pos_x = max(10, screen_w - self.collapsed_w - 20)
        pos_y = max(10, screen_h - self.collapsed_h - 50)
        self.geometry(f'{self.collapsed_w}x{self.collapsed_h}+{pos_x}+{pos_y}')

    def _set_expanded_geometry(self):
        screen_w, screen_h = self._get_safe_screen_bounds()
        pos_x = max(10, screen_w - self.expanded_w - 20)
        pos_y = max(10, screen_h - self.expanded_h - 50)
        self.geometry(f'{self.expanded_w}x{self.expanded_h}+{pos_x}+{pos_y}')

    def _get_theme_accent(self) -> str:
        conf = AVATAR_CONFIGS.get(self.avatar_type.lower(), {})
        return conf.get('accent', '#3B8ED0')

    def _build_ui(self):
        accent_color = self._get_theme_accent()

        self.container = ctk.CTkFrame(
            self,
            fg_color=('#1E1E1E', '#181818'),
            corner_radius=18,
            border_width=2,
            border_color=accent_color
        )
        self.container.pack(fill='both', expand=True, padx=2, pady=2)

        # 1. COLLAPSED VIEW: Large centered pet + Name badge
        self.collapsed_frame = ctk.CTkFrame(self.container, fg_color='transparent')
        
        self.avatar_label_collapsed = ctk.CTkLabel(self.collapsed_frame, text='', cursor='hand2')
        self.avatar_label_collapsed.pack(pady=(6, 2))

        self.name_badge = ctk.CTkLabel(
            self.collapsed_frame,
            text=f'🐾 {self.avatar_name}',
            font=ctk.CTkFont(size=12, weight='bold'),
            text_color='#90CAF9',
            fg_color=('#263238', '#212121'),
            corner_radius=8,
            padx=8,
            pady=2,
            cursor='hand2'
        )
        self.name_badge.pack(pady=(0, 6))

        # 2. EXPANDED VIEW: Header row + Body text + Action buttons
        self.expanded_frame = ctk.CTkFrame(self.container, fg_color='transparent')

        self.avatar_header = ctk.CTkFrame(self.expanded_frame, fg_color='transparent')
        self.avatar_header.pack(fill='x', padx=8, pady=(6, 4))

        self.avatar_label_expanded = ctk.CTkLabel(self.avatar_header, text='', cursor='hand2')
        self.avatar_label_expanded.pack(side='left', padx=(0, 6))

        self.name_lbl = ctk.CTkLabel(
            self.avatar_header,
            text=self.avatar_name,
            font=ctk.CTkFont(size=14, weight='bold'),
            text_color='#64B5F6'
        )
        self.name_lbl.pack(side='left')

        self.close_btn = ctk.CTkButton(
            self.avatar_header,
            text='✕',
            width=26,
            height=26,
            fg_color='transparent',
            hover_color='#37474F',
            font=ctk.CTkFont(size=12, weight='bold'),
            command=self.collapse_to_idle
        )
        self.close_btn.pack(side='right')

        # Expandable Body
        self.body_frame = ctk.CTkFrame(self.expanded_frame, fg_color='transparent')
        self.body_frame.pack(fill='both', expand=True, padx=4, pady=2)

        self.msg_label = ctk.CTkLabel(
            self.body_frame,
            text='',
            font=ctk.CTkFont(size=13),
            wraplength=380,
            justify='left'
        )
        self.msg_label.pack(fill='x', padx=12, pady=(0, 10))

        # Action Buttons container
        self.action_frame = ctk.CTkFrame(self.body_frame, fg_color='transparent')
        self.action_frame.pack(fill='x', padx=8, pady=(0, 8))

        # Animation Controller linked to the collapsed label initially
        self.anim_ctrl = AnimationController(
            target_label=self.avatar_label_collapsed,
            avatar_type=self.avatar_type,
            initial_state='idle',
            avatar_mgr=self.avatar_mgr,
            frame_size=(74, 74),
            fps=6
        )
        self.anim_ctrl.start()

        # Click handlers to toggle popup
        self.avatar_label_collapsed.bind('<Button-1>', lambda e: self._on_avatar_clicked())
        self.name_badge.bind('<Button-1>', lambda e: self._on_avatar_clicked())
        self.avatar_label_expanded.bind('<Button-1>', lambda e: self._on_avatar_clicked())
        self.name_lbl.bind('<Button-1>', lambda e: self._on_avatar_clicked())

    def _apply_layout_collapsed(self):
        self.is_expanded = False
        self.expanded_frame.pack_forget()
        self.anim_ctrl.target_label = self.avatar_label_collapsed
        self.anim_ctrl.set_frame_size((74, 74))
        self.collapsed_frame.pack(fill='both', expand=True)
        self._set_collapsed_geometry()

    def _apply_layout_expanded(self):
        self.is_expanded = True
        self.collapsed_frame.pack_forget()
        self.anim_ctrl.target_label = self.avatar_label_expanded
        self.anim_ctrl.set_frame_size((52, 52))
        self.expanded_frame.pack(fill='both', expand=True)
        self._set_expanded_geometry()

    def _on_avatar_clicked(self):
        if not self.is_expanded:
            self.show_nudge('energy_checkin')
        else:
            self.collapse_to_idle()

    def show_nudge(self, nudge_type: str, **kwargs):
        """Displays a companion nudge without stealing keyboard focus."""
        try:
            self.current_nudge_type = nudge_type
            active_tone = kwargs.pop('tone', self.tone)
            msg = self.template_engine.render(
                nudge_type,
                tone=active_tone,
                user_name=self.user_name,
                avatar_name=self.avatar_name,
                **kwargs
            )
            self.current_message = msg

            # Update UI content
            self.msg_label.configure(text=msg)
            for ch in self.action_frame.winfo_children():
                ch.destroy()

            if nudge_type == 'energy_checkin':
                self._build_energy_rating_buttons()
            else:
                self._build_nudge_buttons()

            self._apply_layout_expanded()

            # Smooth state transition to alert
            self.anim_ctrl.set_state('alert', play_once=True, on_complete=lambda s: self.anim_ctrl.set_state('waiting_for_response'))

            # Speak voice nudge in background if enabled
            if self.config_mgr.get('tts_enabled', False):
                self.tts_engine.speak(msg)

        except Exception as e:
            logger.error(f"Error displaying nudge in AvatarOverlay: {e}")

    def _build_energy_rating_buttons(self):
        ctk.CTkLabel(
            self.action_frame,
            text='Rate energy (1-5):',
            font=ctk.CTkFont(size=12, weight='bold'),
            text_color='#90CAF9'
        ).pack(side='left', padx=(4, 8))

        colors = ['#E53935', '#FB8C00', '#FDD835', '#7CB342', '#43A047']
        for i in range(1, 6):
            btn = ctk.CTkButton(
                self.action_frame,
                text=str(i),
                width=34,
                height=32,
                fg_color=colors[i-1],
                hover_color='#37474F',
                font=ctk.CTkFont(size=13, weight='bold'),
                command=lambda val=i: self._on_rate_energy(val)
            )
            btn.pack(side='left', padx=3)

    def _build_nudge_buttons(self):
        ctk.CTkButton(
            self.action_frame,
            text='Do it now',
            fg_color='#2E7D32',
            hover_color='#388E3C',
            width=105,
            height=32,
            font=ctk.CTkFont(size=12, weight='bold'),
            command=self._on_act_now
        ).pack(side='left', padx=3, expand=True)

        ctk.CTkButton(
            self.action_frame,
            text='Snooze 10m',
            fg_color='#455A64',
            hover_color='#607D8B',
            width=105,
            height=32,
            font=ctk.CTkFont(size=12),
            command=self._on_snooze
        ).pack(side='left', padx=3, expand=True)

        ctk.CTkButton(
            self.action_frame,
            text='Dismiss',
            fg_color='#37474F',
            hover_color='#424242',
            width=85,
            height=32,
            font=ctk.CTkFont(size=12),
            command=self._on_dismiss
        ).pack(side='left', padx=3, expand=True)

    def _on_rate_energy(self, score: int):
        try:
            self.db_mgr.log_energy(energy_level=score, prompt_type='popup_rating')
        except Exception as e:
            logger.error(f"Error logging energy: {e}")

        celeb = self.template_engine.render('celebrate', tone=self.tone, user_name=self.user_name, avatar_name=self.avatar_name)
        self.msg_label.configure(text=f'Energy rating {score}/5 logged!\n{celeb}')
        
        for ch in self.action_frame.winfo_children():
            ch.destroy()

        self.anim_ctrl.set_state('celebrate', play_once=True)
        self.after(2200, self.collapse_to_idle)

    def _on_act_now(self):
        try:
            self.db_mgr.log_nudge(nudge_type=self.current_nudge_type, message=self.current_message, action='acted')
        except Exception as e:
            logger.error(f"Error logging nudge action: {e}")

        celeb = self.template_engine.render('celebrate', tone=self.tone, user_name=self.user_name, avatar_name=self.avatar_name)
        self.msg_label.configure(text=celeb)

        for ch in self.action_frame.winfo_children():
            ch.destroy()

        self.anim_ctrl.set_state('celebrate', play_once=True)
        self.after(2200, self.collapse_to_idle)

    def _on_snooze(self):
        try:
            self.db_mgr.log_nudge(nudge_type=self.current_nudge_type, message=self.current_message, action='snoozed')
        except Exception as e:
            logger.error(f"Error logging snooze: {e}")
        self.collapse_to_idle()

    def _on_dismiss(self):
        try:
            self.db_mgr.log_nudge(nudge_type=self.current_nudge_type, message=self.current_message, action='dismissed')
        except Exception as e:
            logger.error(f"Error logging dismiss: {e}")
        self.collapse_to_idle()

    def collapse_to_idle(self):
        self.anim_ctrl.set_state('idle')
        self._apply_layout_collapsed()

    def reload_settings(self):
        self.avatar_type = self.config_mgr.get('avatar_type', 'cat')
        self.user_name = self.config_mgr.get('user_name', 'Friend')
        self.avatar_name = self.config_mgr.get('avatar_name', 'Mochi')
        self.tone = self.config_mgr.get('personality_tone', 'chill')
        
        self.name_lbl.configure(text=self.avatar_name)
        self.name_badge.configure(text=f'🐾 {self.avatar_name}')
        self.container.configure(border_color=self._get_theme_accent())
        self.anim_ctrl.set_avatar_type(self.avatar_type)
