import os
import getpass
from typing import Optional, Callable
import customtkinter as ctk

from ..settings.config_manager import ConfigManager, AVATAR_OPTIONS, PERSONALITY_TONES
from ..nudges.template_engine import TemplateEngine

ctk.set_appearance_mode('Dark')
ctk.set_default_color_theme('blue')

class OnboardingWindow(ctk.CTk):
    def __init__(self, config_mgr: Optional[ConfigManager] = None, on_complete: Optional[Callable[[], None]] = None):
        super().__init__()
        self.config_mgr = config_mgr or ConfigManager()
        self.on_complete = on_complete
        self.template_engine = TemplateEngine(config_mgr=self.config_mgr)

        self.title('Welcome to AI DeskMate')
        self.geometry('680x820')
        self.minsize(620, 720)
        self.resizable(True, True)

        # State
        default_user = getpass.getuser().capitalize() or 'Friend'
        self.selected_avatar = ctk.StringVar(value=self.config_mgr.get('avatar_type', 'cat'))
        self.selected_tone = ctk.StringVar(value=self.config_mgr.get('personality_tone', 'chill'))
        self.user_name_var = ctk.StringVar(value=self.config_mgr.get('user_name', default_user))
        self.avatar_name_var = ctk.StringVar(value=self.config_mgr.get('avatar_name', 'Mochi'))

        # Track variable changes for live preview
        self.selected_avatar.trace_add('write', self._update_preview)
        self.selected_tone.trace_add('write', self._update_preview)
        self.user_name_var.trace_add('write', self._update_preview)
        self.avatar_name_var.trace_add('write', self._update_preview)

        self._build_ui()
        self._update_preview()

    def _build_ui(self):
        scroll = ctk.CTkScrollableFrame(self, corner_radius=0)
        scroll.pack(fill='both', expand=True, padx=20, pady=20)

        # 1. Header
        header_frame = ctk.CTkFrame(scroll, fg_color='transparent')
        header_frame.pack(fill='x', pady=(0, 15))
        
        title_lbl = ctk.CTkLabel(header_frame, text='Choose Your DeskMate \n\ud083\udc18', font=ctk.CTkFont(size=24, weight='bold'))
        title_lbl.pack(anchor='w')
        
        sub_lbl = ctk.CTkLabel(header_frame, text='Your personal desktop companion for breaks, posture, water, and focus flow.', font=ctk.CTkFont(size=13), text_color='gray70')
        sub_lbl.pack(anchor='w', pady=(2, 0))

        # 2. Character Selection
        sec1_lbl = ctk.CTkLabel(scroll, text='1. Select Your Character', font=ctk.CTkFont(size=16, weight='bold'))
        sec1_lbl.pack(anchor='w', pady=(10, 8))

        chars_frame = ctk.CTkFrame(scroll)
        chars_frame.pack(fill='x', pady=(0, 15), padx=5)

        for opt in AVATAR_OPTIONS:
            btn = ctk.CTkRadioButton(
                chars_frame,
                text=f"{opt['emoji']} {opt['name']} -  { opt['description'] }",
                value=opt['type'],
                variable=self.selected_avatar,
                font=ctk.CTkFont(size=13),
                command=self._on_avatar_changed
            )
            btn.pack(anchor='w', padx=15, pady=8)

        # 3. Naming
        sec2_lbl = ctk.CTkLabel(scroll, text='2. Names & Identity', font=ctk.CTkFont(size=16, weight='bold'))
        sec2_lbl.pack(anchor='w', pady=(10, 8))

        names_frame = ctk.CTkFrame(scroll)
        names_frame.pack(fill='x', pady=(0, 15), padx=5)

        # User Name
        u_lbl = ctk.CTkLabel(names_frame, text='What should I call you?', font=ctk.CTkFont(size=13))
        u_lbl.pack(anchor='w', padx=15, pady=(10, 2))
        u_entry = ctk.CTkEntry(names_frame, textvariable=self.user_name_var, placeholder_text='Your Name')
        u_entry.pack(fill='x', padx=15, pady=(0, 10))

        # Avatar Name + Randomize Button
        a_lbl = ctk.CTkLabel(names_frame, text='What do you want to name your DeskMate?', font=ctk.CTkFont(size=13))
        a_lbl.pack(anchor='w', padx=15, pady=(5, 2))
        
        avatar_row = ctk.CTkFrame(names_frame, fg_color='transparent')
        avatar_row.pack(fill='x', padx=15, pady=(0, 12))
        
        a_entry = ctk.CTkEntry(avatar_row, textvariable=self.avatar_name_var, placeholder_text='DeskMate Name')
        a_entry.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        rnd_btn = ctk.CTkButton(avatar_row, text='\ud083\udc12 Surprise Me', width=120, command=self._randomize_avatar_name)
        rnd_btn.pack(side='right')

        # 4. Personality Tone
        sec3_lbl = ctk.CTkLabel(scroll, text='3. Personality Tone', font=ctk.CTkFont(size=16, weight='bold'))
        sec3_lbl.pack(anchor='w', pady=(10, 8))

        tone_frame = ctk.CTkFrame(scroll)
        tone_frame.pack(fill='x', pady=(0, 15), padx=5)

        for tone in PERSONALITY_TONES:
            t_btn = ctk.CTkRadioButton(
                tone_frame,
                text=f"{tone['name']} -- {tone['tagline']}",
                value=tone['id'],
                variable=self.selected_tone,
                font=ctk.CTkFont(size=13)
            )
            t_btn.pack(anchor='w', padx=15, pady=8)

        # 5. Live Preview Card
        sec4_lbl = ctk.CTkLabel(scroll, text='\m2728 Live Message Preview', font=ctk.CTkFont(size=16, weight='bold'))
        sec4_lbl.pack(anchor='w', pady=(10, 8))

        self.preview_frame = ctk.CTkFrame(scroll, fg_color=('#2B2B2B', '#1E1E1E'), border_width=1, border_color='#3B8ED0')
        self.preview_frame.pack(fill='x', pady=(0, 20), padx=5)

        self.preview_label = ctk.CTkLabel(
            self.preview_frame,
            text='',
            font=ctk.CTkFont(size=13, slant='italic'),
            wraplength=550,
            justify='left'
        )
        self.preview_label.pack(padx=20, pady=15, fill='x')

        # 6. Action Button
        submit_btn = ctk.CTkButton(
            scroll,
            text='Save & Launch AI DeskMate \ud083\udc80',
            font=ctk.CTkFont(size=15, weight='bold'),
            height=45,
            command=self._save_and_finish
        )
        submit_btn.pack(fill='x', pady=(5, 15), padx=5)


    def _on_avatar_changed(self):
        av_type = self.selected_avatar.get()
        self.avatar_name_var.set(ConfigManager.get_random_name(av_type))

    def _randomize_avatar_name(self):
        av_type = self.selected_avatar.get()
        self.avatar_name_var.set(ConfigManager.get_random_name(av_type))

    def _update_preview(self, *args):
        u_name = self.user_name_var.get().strip() or 'Friend'
        a_name = self.avatar_name_var.get().strip() or 'DeskMate'
        tone = self.selected_tone.get()
        
        sample = self.template_engine.render(
            'break_reminder',
            tone=tone,
            user_name=u_name,
            avatar_name=a_name,
            minutes=90
        )
        if hasttr(self, 'preview_label'):
            self.preview_label.configure(text=f'"{sample}"')

    def _save_and_finish(self):
        u_name = self.user_name_var.get().strip() or 'Friend'
        a_name = self.avatar_name_var.get().strip() or 'DeskMate'
        av_type = self.selected_avatar.get()
        tone = self.selected_tone.get()

        self.config_mgr.update({
            'onboarding_completed': True,
            'user_name': u_name,
            'avatar_name': a_name,
            'avatar_type': av_type,
            'personality_tone': tone
        })

        self.destroy()
        if self.on_complete:
            self.on_complete()
