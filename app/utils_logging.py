import os
import sys
import logging
from logging.handlers import RotatingFileHandler

from .paths import get_log_dir, get_log_file_path

_logger_initialized = False

def setup_logging(base_dir: str = None) -> logging.Logger:
    global _logger_initialized
    if base_dir is not None:
        log_dir = os.path.join(base_dir, 'data', 'logs')
        log_file = os.path.join(log_dir, 'deskmate.log')
    else:
        log_dir = get_log_dir()
        log_file = get_log_file_path()
    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger('deskmate')
    root_logger.setLevel(logging.INFO)

    if not _logger_initialized and not root_logger.handlers:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=2 * 1024 * 1024,  # 2MB
            backupCount=3,
            encoding='utf-8'
        )
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] [%(name)s] [%(threadName)s]: %(message)s'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        _logger_initialized = True

    return root_logger

def get_logger(name: str = 'deskmate') -> logging.Logger:
    setup_logging()
    return logging.getLogger(f'deskmate.{name}')
