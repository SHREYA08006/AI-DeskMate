import os
import math
from typing import Dict, Optional, List
try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from ..paths import get_assets_dir, get_avatars_dir

ASSETS_DIR = get_assets_dir()
AVATARS_DIR = get_avatars_dir()

AVATAR_CONFIGS = {
    'cat': {'bg': '#FFE0B2', 'accent': '#FF9800', 'text': '#E65100', 'emoji': '🐱', 'name': 'Cat (Mochi)'},
    'dog': {'bg': '#D1C4E9', 'accent': '#673AB7', 'text': '#311B92', 'emoji': '🐶', 'name': 'Dog (Pip)'},
    'hamster': {'bg': '#FFCDD2', 'accent': '#E91E63', 'text': '#880E4F', 'emoji': '🐹', 'name': 'Hamster'},
    'human': {'bg': '#C8E6C9', 'accent': '#4CAF50', 'text': '#1B5E20', 'emoji': '🧑', 'name': 'Human Buddy'},
    'robot': {'bg': '#B3E5FC', 'accent': '#03A9F4', 'text': '#01579B', 'emoji': '🤖', 'name': 'Robo-Buddy'}
}

ANIMATION_STATES = ['idle', 'alert', 'waiting_for_response', 'celebrate']
FRAME_COUNT = 4


class AvatarManager:
    def __init__(self, avatars_dir: Optional[str] = None):
        self.avatars_dir = avatars_dir or get_avatars_dir()
        os.makedirs(self.avatars_dir, exist_ok=True)
        self.ensure_assets()

    def ensure_assets(self, force: bool = False):
        if not PIL_AVAILABLE:
            return

        for av_type, conf in AVATAR_CONFIGS.items():
            type_dir = os.path.join(self.avatars_dir, av_type)
            os.makedirs(type_dir, exist_ok=True)
            for state in ANIMATION_STATES:
                for frame_idx in range(FRAME_COUNT):
                    frame_path = os.path.join(type_dir, f'{state}_{frame_idx}.png')
                    if force or not os.path.exists(frame_path):
                        self._generate_animation_frame(frame_path, av_type, conf, state, frame_idx)

        tray_icon_path = os.path.join(ASSETS_DIR, 'tray_icon.png')
        if force or not os.path.exists(tray_icon_path):
            self._generate_tray_icon(tray_icon_path)

    def _generate_animation_frame(self, file_path: str, av_type: str, conf: dict, state: str, frame: int):
        size = (128, 128)
        img = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        if av_type == 'cat':
            self._draw_cat(draw, state, frame)
        elif av_type == 'dog':
            self._draw_dog(draw, state, frame)
        elif av_type == 'hamster':
            self._draw_hamster(draw, state, frame)
        elif av_type == 'robot':
            self._draw_robot(draw, state, frame)
        else:
            self._draw_human(draw, state, frame)

        self._draw_effects(draw, state, frame)
        img.save(file_path, 'PNG')

    def _draw_cat(self, draw: ImageDraw.ImageDraw, state: str, frame: int):
        bob = int(math.sin(frame * math.pi / 2) * 2) if state == 'idle' else 0
        ear_tw = 3 if (state == 'idle' and frame == 3) else 0
        tail_tw = int(math.sin(frame * math.pi / 2) * 6)
        is_blink = (state == 'idle' and frame == 2)
        is_alert = (state == 'alert')
        is_celebrate = (state == 'celebrate')

        if is_alert:
            bob = -int(abs(math.sin(frame * math.pi / 2)) * 6)
        elif is_celebrate:
            bob = -int(abs(math.sin(frame * math.pi / 2)) * 8)

        c_fur = '#FF9E1B'        # Vibrant warm orange
        c_fur_dark = '#D84315'   # Deep amber outline / stripes
        c_fur_shadow = '#F57C00' # Fur shadow
        c_belly = '#FFFDE7'      # Cream white
        c_ear_inner = '#FF8A80'  # Coral pink
        c_eye_iris = '#2E7D32'   # Emerald cat eye
        c_eye_pupil = '#1A1A1A'
        c_nose = '#FF5252'       # Soft pink nose
        c_blush = '#FFAB91'      # Rosy cheek blush

        cy = 60 + bob

        # 1. TAIL
        tail_pts = [
            (88, cy + 28),
            (108 + tail_tw, cy + 20),
            (118 + tail_tw, cy + 2),
            (110 + tail_tw, cy - 2),
            (96, cy + 18)
        ]
        draw.polygon(tail_pts, fill=c_fur, outline=c_fur_dark)
        draw.ellipse([106 + tail_tw, cy - 6, 120 + tail_tw, cy + 6], fill=c_belly, outline=c_fur_dark, width=1)

        # 2. BODY
        draw.ellipse([26, cy + 10, 102, cy + 58], fill=c_fur, outline=c_fur_dark, width=2)
        draw.ellipse([38, cy + 16, 90, cy + 54], fill=c_belly)

        # 3. POINTED CAT EARS
        draw.polygon([(18, cy - 6), (28, cy - 48 - ear_tw), (58, cy - 18)], fill=c_fur, outline=c_fur_dark)
        draw.polygon([(26, cy - 8), (32, cy - 38 - ear_tw), (50, cy - 18)], fill=c_ear_inner)
        draw.line([(24, cy - 10), (32, cy - 14)], fill=c_belly, width=2)
        draw.line([(28, cy - 6), (36, cy - 10)], fill=c_belly, width=2)

        draw.polygon([(110, cy - 6), (100, cy - 48 + ear_tw), (70, cy - 18)], fill=c_fur, outline=c_fur_dark)
        draw.polygon([(102, cy - 8), (96, cy - 38 + ear_tw), (78, cy - 18)], fill=c_ear_inner)
        draw.line([(104, cy - 10), (96, cy - 14)], fill=c_belly, width=2)
        draw.line([(100, cy - 6), (92, cy - 10)], fill=c_belly, width=2)

        # 4. HEAD WITH CHEEK FUR TUFTS (Unmistakable cat head outline)
        draw.polygon([(20, cy + 2), (6, cy + 10), (22, cy + 18)], fill=c_fur, outline=c_fur_dark)
        draw.polygon([(20, cy + 16), (10, cy + 22), (28, cy + 26)], fill=c_fur, outline=c_fur_dark)
        draw.polygon([(108, cy + 2), (122, cy + 10), (106, cy + 18)], fill=c_fur, outline=c_fur_dark)
        draw.polygon([(108, cy + 16), (118, cy + 22), (100, cy + 26)], fill=c_fur, outline=c_fur_dark)

        draw.ellipse([16, cy - 28, 112, cy + 32], fill=c_fur, outline=c_fur_dark, width=2)

        # Forehead Tabby Stripes (M mark)
        draw.line([(64, cy - 24), (64, cy - 14)], fill=c_fur_dark, width=3)
        draw.line([(56, cy - 22), (54, cy - 14)], fill=c_fur_dark, width=2)
        draw.line([(72, cy - 22), (74, cy - 14)], fill=c_fur_dark, width=2)

        # Cream Muzzle
        draw.ellipse([36, cy - 2, 92, cy + 28], fill=c_belly, outline=c_fur_shadow, width=1)

        # 5. SPARKLING EYES
        if is_blink or is_celebrate:
            draw.arc([34, cy + 2, 54, cy + 16], start=180, end=360, fill=c_fur_dark, width=3)
            draw.arc([74, cy + 2, 94, cy + 16], start=180, end=360, fill=c_fur_dark, width=3)
        else:
            # Left Eye
            draw.ellipse([34, cy - 4, 54, cy + 16], fill=c_eye_iris, outline=c_fur_dark, width=1)
            draw.ellipse([39, cy - 2, 49, cy + 14], fill=c_eye_pupil)
            draw.ellipse([40, cy - 1, 45, cy + 5], fill='#FFFFFF')
            draw.ellipse([46, cy + 8, 49, cy + 12], fill='#FFFFFF')

            # Right Eye
            draw.ellipse([74, cy - 4, 94, cy + 16], fill=c_eye_iris, outline=c_fur_dark, width=1)
            draw.ellipse([79, cy - 2, 89, cy + 14], fill=c_eye_pupil)
            draw.ellipse([80, cy - 1, 85, cy + 5], fill='#FFFFFF')
            draw.ellipse([86, cy + 8, 89, cy + 12], fill='#FFFFFF')

        # 6. BLUSH
        draw.ellipse([24, cy + 10, 38, cy + 20], fill=c_blush)
        draw.ellipse([90, cy + 10, 104, cy + 20], fill=c_blush)

        # 7. NOSE & :3 MOUTH
        draw.polygon([(60, cy + 9), (68, cy + 9), (64, cy + 14)], fill=c_nose)
        draw.arc([54, cy + 11, 64, cy + 21], start=0, end=180, fill=c_fur_dark, width=2)
        draw.arc([64, cy + 11, 74, cy + 21], start=0, end=180, fill=c_fur_dark, width=2)

        # 8. CRISP WHISKERS
        draw.line([(10, cy + 10), (32, cy + 13)], fill=c_fur_dark, width=2)
        draw.line([(8, cy + 17), (32, cy + 17)], fill=c_fur_dark, width=2)
        draw.line([(12, cy + 24), (34, cy + 21)], fill=c_fur_dark, width=2)
        draw.line([(118, cy + 10), (96, cy + 13)], fill=c_fur_dark, width=2)
        draw.line([(120, cy + 17), (96, cy + 17)], fill=c_fur_dark, width=2)
        draw.line([(116, cy + 24), (94, cy + 21)], fill=c_fur_dark, width=2)

        # 9. FRONT PAWS
        paw_y = cy + 42
        if is_celebrate:
            draw.ellipse([24, cy + 6, 42, cy + 22], fill=c_belly, outline=c_fur_dark, width=2)
            draw.ellipse([86, cy + 6, 104, cy + 22], fill=c_belly, outline=c_fur_dark, width=2)
        else:
            draw.ellipse([42, paw_y, 58, paw_y + 16], fill=c_belly, outline=c_fur_dark, width=2)
            draw.line([(47, paw_y + 7), (47, paw_y + 14)], fill=c_fur_dark, width=1)
            draw.line([(53, paw_y + 7), (53, paw_y + 14)], fill=c_fur_dark, width=1)
            draw.ellipse([70, paw_y, 86, paw_y + 16], fill=c_belly, outline=c_fur_dark, width=2)
            draw.line([(75, paw_y + 7), (75, paw_y + 14)], fill=c_fur_dark, width=1)
            draw.line([(81, paw_y + 7), (81, paw_y + 14)], fill=c_fur_dark, width=1)

    def _draw_dog(self, draw: ImageDraw.ImageDraw, state: str, frame: int):
        bob = int(math.sin(frame * math.pi / 2) * 2) if state == 'idle' else 0
        ear_flop = int(math.sin(frame * math.pi / 2) * 4) if state == 'idle' else 0
        tail_swing = int(math.sin(frame * math.pi) * 8)
        is_blink = (state == 'idle' and frame == 2)
        is_alert = (state == 'alert')
        is_celebrate = (state == 'celebrate')

        if is_alert:
            bob = -int(abs(math.sin(frame * math.pi / 2)) * 6)
            ear_flop = -4
        elif is_celebrate:
            bob = -int(abs(math.sin(frame * math.pi / 2)) * 8)

        c_fur = '#FFA726'        # Golden honey coat
        c_fur_dark = '#C67100'   # Outline & shading
        c_ear = '#E65100'        # Rich chestnut floppy ears
        c_muzzle = '#FFF8E1'     # Cream snout & chest
        c_eye_pupil = '#212121'  # Big dark puppy eyes
        c_nose = '#1B1B1B'       # Shiny black dog nose
        c_tongue = '#FF4081'     # Cute pink tongue
        c_blush = '#FFAB91'

        cy = 60 + bob

        # 1. WAGGING TAIL
        tail_pts = [(90, cy + 30), (118 + tail_swing, cy + 10), (98, cy + 40)]
        draw.polygon(tail_pts, fill=c_ear, outline=c_fur_dark)

        # 2. BODY
        draw.ellipse([26, cy + 10, 102, cy + 58], fill=c_fur, outline=c_fur_dark, width=2)
        draw.ellipse([38, cy + 16, 90, cy + 54], fill=c_muzzle)

        # 3. BIG FLOPPY DOG EARS
        draw.ellipse([6, cy - 18 + ear_flop, 36, cy + 34 + ear_flop], fill=c_ear, outline=c_fur_dark, width=2)
        draw.ellipse([12, cy - 10 + ear_flop, 30, cy + 24 + ear_flop], fill='#BF360C')
        draw.ellipse([92, cy - 18 - ear_flop, 122, cy + 34 - ear_flop], fill=c_ear, outline=c_fur_dark, width=2)
        draw.ellipse([98, cy - 10 - ear_flop, 116, cy + 24 - ear_flop], fill='#BF360C')

        # 4. HEAD
        draw.ellipse([20, cy - 26, 108, cy + 32], fill=c_fur, outline=c_fur_dark, width=2)
        draw.ellipse([34, cy - 2, 94, cy + 30], fill=c_muzzle, outline=c_fur_dark, width=1)

        # 5. SPARKLING PUPPY EYES
        if is_blink or is_celebrate:
            draw.arc([36, cy + 2, 54, cy + 16], start=180, end=360, fill=c_fur_dark, width=3)
            draw.arc([74, cy + 2, 92, cy + 16], start=180, end=360, fill=c_fur_dark, width=3)
        else:
            draw.ellipse([36, cy - 4, 54, cy + 14], fill=c_eye_pupil)
            draw.ellipse([38, cy - 2, 45, cy + 5], fill='#FFFFFF')
            draw.ellipse([46, cy + 6, 50, cy + 10], fill='#FFFFFF')

            draw.ellipse([74, cy - 4, 92, cy + 14], fill=c_eye_pupil)
            draw.ellipse([76, cy - 2, 83, cy + 5], fill='#FFFFFF')
            draw.ellipse([84, cy + 6, 88, cy + 10], fill='#FFFFFF')

        # Blush
        draw.ellipse([24, cy + 10, 36, cy + 20], fill=c_blush)
        draw.ellipse([92, cy + 10, 104, cy + 20], fill=c_blush)

        # 6. SHINY BLACK NOSE & MOUTH WITH TONGUE
        draw.ellipse([56, cy + 6, 72, cy + 17], fill=c_nose)
        draw.ellipse([59, cy + 8, 64, cy + 12], fill='#FFFFFF')

        draw.line([(64, cy + 17), (64, cy + 22)], fill=c_fur_dark, width=2)
        draw.arc([52, cy + 15, 64, cy + 25], start=0, end=180, fill=c_fur_dark, width=2)
        draw.arc([64, cy + 15, 76, cy + 25], start=0, end=180, fill=c_fur_dark, width=2)

        # Panting tongue
        draw.ellipse([58, cy + 22, 70, cy + 32], fill=c_tongue, outline='#D81B60', width=1)
        draw.line([(64, cy + 22), (64, cy + 29)], fill='#D81B60', width=1)

        # 7. FRONT PAWS
        paw_y = cy + 42
        if is_celebrate:
            draw.ellipse([24, cy + 6, 42, cy + 22], fill=c_muzzle, outline=c_fur_dark, width=2)
            draw.ellipse([86, cy + 6, 104, cy + 22], fill=c_muzzle, outline=c_fur_dark, width=2)
        else:
            draw.ellipse([42, paw_y, 58, paw_y + 16], fill=c_muzzle, outline=c_fur_dark, width=2)
            draw.line([(47, paw_y + 7), (47, paw_y + 14)], fill=c_fur_dark, width=1)
            draw.line([(53, paw_y + 7), (53, paw_y + 14)], fill=c_fur_dark, width=1)

            draw.ellipse([70, paw_y, 86, paw_y + 16], fill=c_muzzle, outline=c_fur_dark, width=2)
            draw.line([(75, paw_y + 7), (75, paw_y + 14)], fill=c_fur_dark, width=1)
            draw.line([(81, paw_y + 7), (81, paw_y + 14)], fill=c_fur_dark, width=1)

    def _draw_hamster(self, draw: ImageDraw.ImageDraw, state: str, frame: int):
        bob_y = int(math.sin(frame * math.pi / 2) * 2) if state == 'idle' else 0
        cy = 60 + bob_y
        c_body = '#F8BBD0'
        c_dark = '#C2185B'
        c_belly = '#FFF0F5'

        draw.ellipse([26, cy - 36, 48, cy - 14], fill=c_body, outline=c_dark, width=2)
        draw.ellipse([32, cy - 30, 42, cy - 20], fill='#FF80AB')
        draw.ellipse([80, cy - 36, 102, cy - 14], fill=c_body, outline=c_dark, width=2)
        draw.ellipse([86, cy - 30, 96, cy - 20], fill='#FF80AB')

        draw.ellipse([20, cy - 24, 108, cy + 50], fill=c_body, outline=c_dark, width=2)
        draw.ellipse([34, cy - 8, 94, cy + 44], fill=c_belly)

        draw.ellipse([42, cy, 52, cy + 10], fill='#212121')
        draw.ellipse([44, cy + 1, 47, cy + 4], fill='#FFFFFF')
        draw.ellipse([76, cy, 86, cy + 10], fill='#212121')
        draw.ellipse([78, cy + 1, 81, cy + 4], fill='#FFFFFF')

        draw.polygon([(62, cy + 8), (66, cy + 8), (64, cy + 11)], fill='#FF4081')
        draw.rectangle([61, cy + 13, 64, cy + 18], fill='#FFFFFF', outline=c_dark)
        draw.rectangle([64, cy + 13, 67, cy + 18], fill='#FFFFFF', outline=c_dark)

        draw.ellipse([24, cy + 6, 38, cy + 18], fill='#FF80AB')
        draw.ellipse([90, cy + 6, 104, cy + 18], fill='#FF80AB')

    def _draw_robot(self, draw: ImageDraw.ImageDraw, state: str, frame: int):
        bob_y = int(math.sin(frame * math.pi / 2) * 2) if state == 'idle' else 0
        cy = 60 + bob_y
        c_body = '#90CAF9'
        c_dark = '#1565C0'
        c_screen = '#263238'
        c_eye = '#00E676'

        draw.line([(64, cy - 24), (64, cy - 38)], fill=c_dark, width=3)
        draw.ellipse([58, cy - 46, 70, cy - 34], fill='#FF5252', outline=c_dark, width=2)

        draw.rounded_rectangle([28, cy - 24, 100, cy + 24], radius=10, fill=c_body, outline=c_dark, width=3)
        draw.rounded_rectangle([36, cy - 14, 92, cy + 14], radius=6, fill=c_screen)

        draw.ellipse([44, cy - 6, 56, cy + 6], fill=c_eye)
        draw.ellipse([72, cy - 6, 84, cy + 6], fill=c_eye)

        draw.rectangle([20, cy - 6, 28, cy + 6], fill=c_dark)
        draw.rectangle([100, cy - 6, 108, cy + 6], fill=c_dark)

        draw.rounded_rectangle([36, cy + 28, 92, cy + 54], radius=6, fill=c_body, outline=c_dark, width=2)

    def _draw_human(self, draw: ImageDraw.ImageDraw, state: str, frame: int):
        bob_y = int(math.sin(frame * math.pi / 2) * 2) if state == 'idle' else 0
        cy = 60 + bob_y
        c_skin = '#FFE0B2'
        c_hair = '#5D4037'
        c_shirt = '#81C784'

        draw.ellipse([32, cy - 24, 96, cy + 32], fill=c_skin)
        draw.chord([30, cy - 32, 98, cy + 6], start=180, end=360, fill=c_hair)

        draw.ellipse([46, cy + 2, 54, cy + 10], fill='#212121')
        draw.ellipse([74, cy + 2, 82, cy + 10], fill='#212121')
        draw.arc([56, cy + 10, 72, cy + 22], start=0, end=180, fill='#D84315', width=2)

        draw.ellipse([30, cy + 26, 98, cy + 60], fill=c_shirt)

    def _draw_effects(self, draw: ImageDraw.ImageDraw, state: str, frame: int):
        if state == 'alert':
            draw.ellipse([98, 4, 126, 32], fill='#FF1744', outline='#FFFFFF', width=2)
            draw.line([(112, 10), (112, 21)], fill='#FFFFFF', width=3)
            draw.ellipse([110, 24, 114, 28], fill='#FFFFFF')
        elif state == 'celebrate':
            for sx, sy in [(14, 14), (114, 14), (10, 60), (118, 60)]:
                draw.line([(sx-4, sy), (sx+4, sy)], fill='#FFD700', width=2)
                draw.line([(sx, sy-4), (sx, sy+4)], fill='#FFD700', width=2)

    def _generate_tray_icon(self, file_path: str):
        size = (64, 64)
        img = Image.new('RGBA', size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        c_fur = '#FFA726'
        c_dark = '#E65100'
        c_inner = '#FF8A80'

        draw.polygon([(10, 24), (16, 6), (32, 18)], fill=c_fur, outline=c_dark)
        draw.polygon([(14, 22), (18, 10), (28, 18)], fill=c_inner)
        draw.polygon([(54, 24), (48, 6), (32, 18)], fill=c_fur, outline=c_dark)
        draw.polygon([(50, 22), (46, 10), (36, 18)], fill=c_inner)

        draw.ellipse([8, 14, 56, 58], fill=c_fur, outline=c_dark, width=2)
        draw.ellipse([20, 32, 44, 52], fill='#FFF3E0')
        draw.ellipse([20, 26, 28, 34], fill='#2E7D32')
        draw.ellipse([22, 27, 25, 30], fill='#FFFFFF')
        draw.ellipse([36, 26, 44, 34], fill='#2E7D32')
        draw.ellipse([38, 27, 41, 30], fill='#FFFFFF')
        draw.polygon([(30, 37), (34, 37), (32, 40)], fill='#FF5252')
        draw.line([(6, 36), (16, 38)], fill=c_dark, width=1)
        draw.line([(6, 42), (16, 42)], fill=c_dark, width=1)
        draw.line([(58, 36), (48, 38)], fill=c_dark, width=1)
        draw.line([(58, 42), (48, 42)], fill=c_dark, width=1)

        img.save(file_path, 'PNG')

    def get_animation_frames(self, avatar_type: str, state: str = 'idle') -> List[str]:
        type_dir = os.path.join(self.avatars_dir, avatar_type.lower())
        frames = []
        for i in range(FRAME_COUNT):
            p = os.path.join(type_dir, f'{state}_{i}.png')
            if os.path.exists(p):
                frames.append(p)
        if not frames:
            self.ensure_assets()
            for j in range(FRAME_COUNT):
                p = os.path.join(type_dir, f'{state}_{j}.png')
                if os.path.exists(p):
                    frames.append(p)
        return frames

    def get_avatar_image_path(self, avatar_type: str, state: str = 'idle') -> Optional[str]:
        frames = self.get_animation_frames(avatar_type, state)
        return frames[0] if frames else None

    def get_tray_icon_path(self) -> str:
        tray_path = os.path.join(ASSETS_DIR, 'tray_icon.png')
        if not os.path.exists(tray_path):
            self.ensure_assets()
        return tray_path
