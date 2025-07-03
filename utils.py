"""
Yardımcı Fonksiyonlar
"""

import logging
import os
import sys
from datetime import datetime
import config


logger = logging.getLogger(__name__)

def setup_logging():
    """Logging ayarlarını yapılandır"""
    # Log formatı
    log_format = '%(asctime)s - %(levelname)s - %(module)s - %(message)s'

    # Logging seviyesini belirle
    level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

    # Basic config
    logging.basicConfig(
        level=level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(config.LOG_FILE, encoding='utf-8')
        ]
    )

    # Telethon loglarını sessiz yap
    logging.getLogger('telethon').setLevel(logging.WARNING)

def format_time_remaining(seconds: int) -> str:
    """Kalan süreyi formatla"""
    if seconds < 60:
        return f"{seconds} saniye"
    elif seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} dakika"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} saat {minutes} dakika"

def check_session_files() -> list:
    """Mevcut session dosyalarını kontrol et"""
    session_files = []

    # Farklı patterns'ı kontrol et
    import glob
    patterns = ["*.session", "hesap*.session", "account*.session"]

    for pattern in patterns:
        session_files.extend(glob.glob(pattern))

    return sorted(list(set(session_files)))

def parse_env_list(env_var: str, separator: str = ',') -> list:
    """Environment variable'ı liste olarak parse et"""
    value = os.getenv(env_var, '')
    if not value.strip():
        return []
    return [item.strip() for item in value.split(separator) if item.strip()]

def parse_env_bool(env_var: str, default: bool = False) -> bool:
    """Environment variable'ı boolean olarak parse et"""
    value = os.getenv(env_var, str(default)).lower()
    return value in ['true', '1', 'yes', 'on', 'enable', 'enabled']

def parse_env_int(env_var: str, default: int = 0) -> int:
    """Environment variable'ı integer olarak parse et"""
    try:
        return int(os.getenv(env_var, str(default)))
    except ValueError:
        return default
