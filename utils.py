"""
Yardımcı Fonksiyonlar - DÜZELTILMIŞ VERSİYON
"""

import logging
import os
import sys
import glob
from datetime import datetime
from typing import List, Union, Optional, Dict, Any
import config

logger = logging.getLogger(__name__)

def setup_logging():
    """Logging ayarlarını yapılandır"""
    try:
        # Log formatı
        log_format = '%(asctime)s - %(levelname)s - %(module)s:%(lineno)d - %(message)s'

        # Logging seviyesini belirle
        level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)

        # Handlers listesi
        handlers = []

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter(log_format))
        handlers.append(console_handler)

        # File handler (eğer log dosyası yazılabilirse)
        try:
            file_handler = logging.FileHandler(config.LOG_FILE, encoding='utf-8')
            file_handler.setFormatter(logging.Formatter(log_format))
            handlers.append(file_handler)
        except (PermissionError, OSError) as e:
            print(f"⚠️ Log dosyası oluşturulamadı: {e}")

        # Basic config
        logging.basicConfig(
            level=level,
            format=log_format,
            handlers=handlers,
            force=True  # Override existing handlers
        )

        # Telethon loglarını sessiz yap
        logging.getLogger('telethon').setLevel(logging.WARNING)
        logging.getLogger('telethon.network').setLevel(logging.ERROR)
        logging.getLogger('telethon.crypto').setLevel(logging.ERROR)

        # PostgreSQL loglarını da sessiz yap
        logging.getLogger('psycopg2').setLevel(logging.WARNING)

        logger.info(f"✅ Logging kuruldu - Level: {config.LOG_LEVEL}")

    except Exception as e:
        print(f"❌ Logging setup hatası: {e}")

def format_time_remaining(seconds: Union[int, float]) -> str:
    """Kalan süreyi formatla"""
    try:
        if not seconds or seconds <= 0:
            return "0 saniye"

        seconds = int(seconds)

        if seconds < 60:
            return f"{seconds} saniye"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            if remaining_seconds > 0:
                return f"{minutes} dakika {remaining_seconds} saniye"
            return f"{minutes} dakika"
        elif seconds < 86400:  # 24 saat
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            if minutes > 0:
                return f"{hours} saat {minutes} dakika"
            return f"{hours} saat"
        else:
            days = seconds // 86400
            hours = (seconds % 86400) // 3600
            if hours > 0:
                return f"{days} gün {hours} saat"
            return f"{days} gün"

    except Exception as e:
        logger.error(f"Time formatting hatası: {e}")
        return "Hesaplanamadı"

def check_session_files() -> List[str]:
    """Mevcut session dosyalarını kontrol et"""
    try:
        session_files = []

        # Farklı patterns'ı kontrol et
        patterns = ["*.session", "hesap*.session", "account*.session"]

        for pattern in patterns:
            found_files = glob.glob(pattern)
            session_files.extend(found_files)

        # Benzersiz dosyaları al
        unique_files = sorted(list(set(session_files)))

        # Dosyaların geçerliliğini kontrol et
        valid_files = []
        for file_path in unique_files:
            try:
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    # Dosyanın okunabilir olduğunu kontrol et
                    with open(file_path, 'rb') as f:
                        f.read(1)  # İlk byte'ı oku
                    valid_files.append(file_path)
                    logger.debug(f"✅ Geçerli session: {file_path}")
                else:
                    logger.warning(f"⚠️ Geçersiz session dosyası: {file_path}")
            except Exception as e:
                logger.warning(f"⚠️ Session dosyası okunamıyor {file_path}: {e}")

        logger.info(f"📁 {len(valid_files)} geçerli session dosyası bulundu")
        return valid_files

    except Exception as e:
        logger.error(f"❌ Session dosyası kontrolü hatası: {e}")
        return []

def parse_env_list(env_var: str, separator: str = ',') -> List[str]:
    """Environment variable'ı liste olarak parse et"""
    try:
        value = os.getenv(env_var, '').strip()
        if not value:
            return []

        items = [item.strip() for item in value.split(separator) if item.strip()]
        return items

    except Exception as e:
        logger.error(f"Env list parsing hatası {env_var}: {e}")
        return []

def parse_env_bool(env_var: str, default: bool = False) -> bool:
    """Environment variable'ı boolean olarak parse et"""
    try:
        value = os.getenv(env_var, str(default)).lower().strip()
        return value in ['true', '1', 'yes', 'on', 'enable', 'enabled']
    except Exception as e:
        logger.error(f"Env bool parsing hatası {env_var}: {e}")
        return default

def parse_env_int(env_var: str, default: int = 0) -> int:
    """Environment variable'ı integer olarak parse et"""
    try:
        value = os.getenv(env_var, str(default)).strip()
        return int(value)
    except (ValueError, TypeError) as e:
        logger.error(f"Env int parsing hatası {env_var}: {e}")
        return default

def parse_env_float(env_var: str, default: float = 0.0) -> float:
    """Environment variable'ı float olarak parse et"""
    try:
        value = os.getenv(env_var, str(default)).strip()
        return float(value)
    except (ValueError, TypeError) as e:
        logger.error(f"Env float parsing hatası {env_var}: {e}")
        return default

def validate_phone_number(phone: str) -> bool:
    """Telefon numarası doğrulaması"""
    try:
        if not phone:
            return False

        # Basit doğrulama
        cleaned = phone.replace('+', '').replace(' ', '').replace('-', '')
        return cleaned.isdigit() and 10 <= len(cleaned) <= 15

    except Exception:
        return False

def validate_user_id(user_id: Union[int, str, None]) -> bool:
    """User ID doğrulaması"""
    try:
        if user_id is None:
            return False

        user_id = int(user_id)
        return 1 <= user_id <= 9999999999999999999

    except (ValueError, TypeError):
        return False

def format_number(number: Union[int, float], decimals: int = 0) -> str:
    """Sayıyı formatla (thousand separator ile)"""
    try:
        if decimals > 0:
            return f"{number:,.{decimals}f}"
        else:
            return f"{int(number):,}"
    except Exception:
        return str(number)

def calculate_success_rate(successful: int, total: int) -> float:
    """Başarı oranını hesapla"""
    try:
        if total <= 0:
            return 100.0
        return round((successful / total) * 100, 2)
    except Exception:
        return 0.0

def safe_filename(filename: str) -> str:
    """Güvenli dosya adı oluştur"""
    try:
        # Geçersiz karakterleri temizle
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')

        # Çok uzun dosya adlarını kısalt
        if len(filename) > 200:
            filename = filename[:200]

        return filename.strip()

    except Exception:
        return "default_filename"

def get_file_size_mb(file_path: str) -> float:
    """Dosya boyutunu MB olarak getir"""
    try:
        if os.path.exists(file_path):
            size_bytes = os.path.getsize(file_path)
            return round(size_bytes / (1024 * 1024), 2)
        return 0.0
    except Exception:
        return 0.0

def create_backup_filename(original_path: str) -> str:
    """Backup dosya adı oluştur"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name, ext = os.path.splitext(original_path)
        return f"{name}_backup_{timestamp}{ext}"
    except Exception:
        return f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bak"

def ensure_directory_exists(directory_path: str) -> bool:
    """Dizinin var olduğundan emin ol, yoksa oluştur"""
    try:
        if not os.path.exists(directory_path):
            os.makedirs(directory_path, exist_ok=True)
            logger.debug(f"📁 Dizin oluşturuldu: {directory_path}")
        return True
    except Exception as e:
        logger.error(f"❌ Dizin oluşturma hatası {directory_path}: {e}")
        return False

def clean_text(text: str, max_length: Optional[int] = None) -> str:
    """Metni temizle ve formatla"""
    try:
        if not text:
            return ""

        # Whitespace'leri temizle
        cleaned = ' '.join(text.split())

        # Maksimum uzunluk kontrolü
        if max_length and len(cleaned) > max_length:
            cleaned = cleaned[:max_length-3] + "..."

        return cleaned

    except Exception:
        return str(text) if text else ""

def is_valid_url(url: str) -> bool:
    """URL doğrulaması"""
    try:
        if not url:
            return False

        url = url.strip().lower()
        return url.startswith(('http://', 'https://'))

    except Exception:
        return False

def get_system_info() -> Dict[str, Any]:
    """Sistem bilgilerini getir"""
    try:
        import platform
        import psutil

        return {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent if os.name != 'nt' else psutil.disk_usage('C:\\').percent
        }
    except ImportError:
        return {
            'platform': 'Unknown',
            'python_version': sys.version.split()[0],
            'cpu_percent': 0,
            'memory_percent': 0,
            'disk_usage': 0
        }
    except Exception as e:
        logger.error(f"System info hatası: {e}")
        return {}

def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """String'i belirtilen uzunlukta kes"""
    try:
        if not text or len(text) <= max_length:
            return text

        return text[:max_length-len(suffix)] + suffix

    except Exception:
        return str(text)[:max_length] if text else ""

def format_timestamp(timestamp: Optional[datetime] = None, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Timestamp'i formatla"""
    try:
        if timestamp is None:
            timestamp = datetime.now()
        return timestamp.strftime(format_str)
    except Exception:
        return "Unknown"

def parse_duration_string(duration_str: str) -> int:
    """Duration string'ini saniyeye çevir (örn: "1h30m" -> 5400)"""
    try:
        duration_str = duration_str.lower().strip()
        total_seconds = 0

        # Saat
        if 'h' in duration_str:
            hours = int(duration_str.split('h')[0])
            total_seconds += hours * 3600
            duration_str = duration_str.split('h')[1]

        # Dakika
        if 'm' in duration_str:
            minutes = int(duration_str.split('m')[0])
            total_seconds += minutes * 60
            duration_str = duration_str.split('m')[1]

        # Saniye
        if 's' in duration_str:
            seconds = int(duration_str.split('s')[0])
            total_seconds += seconds
        elif duration_str.isdigit():
            total_seconds += int(duration_str)

        return total_seconds

    except Exception as e:
        logger.error(f"Duration parsing hatası: {e}")
        return 0

def create_progress_bar(current: int, total: int, width: int = 20) -> str:
    """ASCII progress bar oluştur"""
    try:
        if total <= 0:
            return "[" + "=" * width + "]"

        progress = min(current / total, 1.0)
        filled = int(width * progress)
        bar = "=" * filled + "-" * (width - filled)
        percentage = int(progress * 100)

        return f"[{bar}] {percentage}% ({current}/{total})"

    except Exception:
        return f"[{'?' * width}] ?% ({current}/{total})"

def rate_limit_check(last_time: Optional[datetime], min_interval: int) -> bool:
    """Rate limit kontrolü"""
    try:
        if last_time is None:
            return True

        elapsed = (datetime.now() - last_time).total_seconds()
        return elapsed >= min_interval

    except Exception:
        return True

# Backward compatibility
def check_required_files() -> bool:
    """Gerekli dosyaların varlığını kontrol et"""
    try:
        session_files = check_session_files()
        return len(session_files) > 0
    except Exception as e:
        logger.error(f"Required files check hatası: {e}")
        return False
