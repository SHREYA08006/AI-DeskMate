from .avatar_manager import AvatarManager, AVATAR_CONFIGS, ANIMATION_STATES

try:
    from .animation_controller import AnimationController
except ImportError:
    AnimationController = None

__all__ = ["AvatarManager", "AVATAR_CONFIGS", "ANIMATION_STATES", "AnimationController"]
