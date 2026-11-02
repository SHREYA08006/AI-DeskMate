import os
import time
from typing import Optional, Callable, Dict, List
import customtkinter as ctk
from PIL import Image

from .avatar_manager import AvatarManager, FRAME_COUNT

class AnimationController:
    def __init__(self,
                 target_label: ctk.CTkLabel,
                 avatar_type: str = 'cat',
                 initial_state: str = 'idle',
                 avatar_mgr: Optional[AvatarManager] = None,
                 frame_size: tuple = (48, 48),
                 fps: int = 5):
        self.target_label = target_label
        self.avatar_type = avatar_type
        self.avatar_mgr = avatar_mgr or AvatarManager()
        self.frame_size = frame_size
        self.fps = fps
        self.frame_interval_ms = int(1000 / fps)

        self.current_state = initial_state
        self.current_frame_index = 0
        self.is_running = False
        self._after_id = None
        self._cached_images: Dict[str, List[ctk.CTkImage]] = {}

        self.on_animation_complete: Optional[Callable[[str], None]] = None
        self._play_once = False

        self._preload_frames()

    def _preload_frames(self):
        for state in ['idle', 'alert', 'waiting_for_response', 'celebrate']:
            frame_paths = self.avatar_mgr.get_animation_frames(self.avatar_type, state)
            ctk_imgs = []
            for fp in frame_paths:
                try:
                    pil_img = Image.open(fp)
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=self.frame_size)
                    ctk_imgs.append(ctk_img)
                except Exception as e:
                    print(f'Error loading frame {fp}: {e}')
            self._cached_images[state] = ctk_imgs

    def set_avatar_type(self, avatar_type: str):
        if self.avatar_type != avatar_type:
            self.avatar_type = avatar_type
            self._cached_images.clear()
            self._preload_frames()
            self._update_current_frame()

    def set_frame_size(self, frame_size: tuple):
        if self.frame_size != frame_size:
            self.frame_size = frame_size
            self._cached_images.clear()
            self._preload_frames()
            self._update_current_frame()

    def set_state(self, new_state: str, play_once: bool = False, on_complete: Optional[Callable[[str], None]] = None):
        if new_state not in self._cached_images:
            return
        
        self.current_state = new_state
        self.current_frame_index = 0
        self._play_once = play_once
        self.on_animation_complete = on_complete
        self._update_current_frame()

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._step()

    def stop(self):
        self.is_running = False
        if self._after_id and hasattr(self.target_label, 'after_cancel'):
            try:
                self.target_label.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _step(self):
        if not self.is_running:
            return

        frames = self._cached_images.get(self.current_state, [])
        if frames:
            self.current_frame_index += 1
            if self.current_frame_index >= len(frames):
                if self._play_once:
                    self.current_frame_index = len(frames) - 1
                    if self.on_animation_complete:
                        cbtn = self.on_animation_complete
                        self.on_animation_complete = None
                        cbtn(self.current_state)
                    return
                else:
                    self.current_frame_index = 0
            self._update_current_frame()

        if hasattr(self.target_label, 'after'):
            self._after_id = self.target_label.after(self.frame_interval_ms, self._step)

    def _update_current_frame(self):
        frames = self._cached_images.get(self.current_state, [])
        if frames and self.current_frame_index < len(frames):
            try:
                self.target_label.configure(image=frames[self.current_frame_index], text='')
            except Exception:
                pass
