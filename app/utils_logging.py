import os
import sys
import logging
from logging.handlers import RotatingFileHandler

from .paths import get_log_dir, get_log_file_path

_logger_initialized = False

def setup_logging(base_dir: str = None) -> logging.Logger:
    global _logger_initialized
    root_logger = logging.getLogger('deskmate')
    root_logger.setLevel(logging.INFO)

    if _logger_initialized or root_logger.handlers:
        return root_logger

    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] [%(name)s] [%(threadName)s]: %(message)s'
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    if base_dir is not None:
        log_dir = os.path.join(base_dir, 'data', 'logs')
        log_file = os.path.join(log_dir, 'deskmate.log')
    else:
        try:
            log_dir = get_log_dir()
            log_file = get_log_file_path()
        except Exception:
            log_dir = None
            log_file = None

    if log_dir and log_file:
        try:
            os.makedirs(log_dir, exist_ok=True)
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=2 * 1024 * 1024,  # 2MB
                backupCount=3,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.debug(f"Could not initialize file logging to {log_file}: {e}")

    _logger_initialized = True
    return root_logger

def get_logger(name: str = 'deskmate') -> logging.Logger:
    setup_logging()
    return logging.getLogger(f'deskmate.{name}')
