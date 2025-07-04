"""
Telegram Mass Messenger Konfigürasyonu - GÜVENLIK DÜZELTMESİ
Environment variables ile güvenli konfigürasyon
"""

import os

# =============================================================================
# ANA HESAP BİLGİLERİ (GÜVENLİ)
# =============================================================================

# Collector hesap API ayarları - Environment variables'dan al
COLLECTOR_API_ID = int(os.getenv('COLLECTOR_API_ID', '0'))
COLLECTOR_API_HASH = os.getenv('COLLECTOR_API_HASH', '')
COLLECTOR_SESSION = os.getenv('COLLECTOR_SESSION', 'hesap1')

# İzlenecek gruplar
COLLECTOR_GROUPS = os.getenv('COLLECTOR_GROUPS', '@CSSAGO').split(',')

# Status raporu ayarları
STATUS_USER_ID = int(os.getenv('STATUS_USER_ID', '0'))
STATUS_USERNAME = os.getenv('STATUS_USERNAME', None)
STATUS_INTERVAL = int(os.getenv('STATUS_INTERVAL', '3600'))

# Sender hesapları - Dynamic loading
def load_sender_accounts():
    """Sender hesaplarını environment'dan yükle"""
    accounts = []
    i = 1
    while True:
        api_id = os.getenv(f'SENDER{i}_API_ID')
        api_hash = os.getenv(f'SENDER{i}_API_HASH')
        session_name = os.getenv(f'SENDER{i}_SESSION')

        if not all([api_id, api_hash, session_name]):
            break

        try:
            accounts.append({
                'number': i,
                'api_id': int(api_id),
                'api_hash': api_hash,
                'session_name': session_name
            })
            i += 1
        except ValueError:
            break

    return accounts

SENDER_ACCOUNTS = load_sender_accounts()

# Fallback for local development (remove in production)
if not SENDER_ACCOUNTS and COLLECTOR_API_ID == 0:
    print("⚠️ WARNING: Using fallback credentials for development")
    COLLECTOR_API_ID = 25846490
    COLLECTOR_API_HASH = "63e7242d97fd985c2287a36a5355f100"
    SENDER_ACCOUNTS = [{
        'number': 1,
        'api_id': 22268590,
        'api_hash': "1e50437dc8deb030023ab1692ba40992",
        'session_name': "hesap2"
    }]

# =============================================================================
# MESAJ AYARLARI
# =============================================================================

BASE_MESSAGE = os.getenv('BASE_MESSAGE', 'MERHABA NASILSINIZ SAGO')

MESSAGE_PREFIXES = [
    "Merhaba ", "Selam ", "İyi günler ", "Selam dostum ", "Hey ",
    "Selamlar ", "İyi akşamlar ", "Merhabalar ", "Nasılsın ",
    "Selam kardeşim ", "İyi günler dostum ", "Merhaba arkadaşım "
]

MESSAGE_SUFFIXES = [
    " 😊", " 👋", "...", " dostum", " arkadaşım", " 🙂",
    " ne dersin?", " bakar mısın?", " 📱", " nasıl gidiyor?",
    " 🤝", " 💪", " ✨", " 🔥", " 👍", " 💯"
]

# =============================================================================
# RATE LIMITING AYARLARI
# =============================================================================

MESSAGE_DELAY_MIN = int(os.getenv('MESSAGE_DELAY_MIN', '45'))
MESSAGE_DELAY_MAX = int(os.getenv('MESSAGE_DELAY_MAX', '90'))
ACCOUNT_SWITCH_DELAY = int(os.getenv('ACCOUNT_SWITCH_DELAY', '15'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '10'))
MESSAGES_PER_HOUR = int(os.getenv('MESSAGES_PER_HOUR', '80'))

# =============================================================================
# COLLECTOR AYARLARI
# =============================================================================

COLLECT_HISTORY_HOURS = int(os.getenv('COLLECT_HISTORY_HOURS', '0'))
COLLECT_LIMIT_PER_GROUP = int(os.getenv('COLLECT_LIMIT_PER_GROUP', '0'))
LIVE_ONLY_MODE = os.getenv('LIVE_ONLY_MODE', 'True').lower() == 'true'
SKIP_HISTORY_SCAN = os.getenv('SKIP_HISTORY_SCAN', 'True').lower() == 'true'

# =============================================================================
# İŞ AKIŞI AYARLARI
# =============================================================================

WORK_MODE = os.getenv('WORK_MODE', 'auto')
AUTO_COLLECT_DURATION = int(os.getenv('AUTO_COLLECT_DURATION', '300'))
AUTO_SEND_DURATION = int(os.getenv('AUTO_SEND_DURATION', '1800'))

# =============================================================================
# VERİTABANI AYARLARI
# =============================================================================

DATABASE_URL = os.getenv('DATABASE_URL')

# =============================================================================
# HATA YÖNETİMİ
# =============================================================================

MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
RETRY_DELAY = int(os.getenv('RETRY_DELAY', '15'))
VALIDATE_ENTITIES = os.getenv('VALIDATE_ENTITIES', 'True').lower() == 'true'
SKIP_INVALID_USERS = os.getenv('SKIP_INVALID_USERS', 'True').lower() == 'true'
CONNECTION_TIMEOUT = int(os.getenv('CONNECTION_TIMEOUT', '30'))
MESSAGE_TIMEOUT = int(os.getenv('MESSAGE_TIMEOUT', '30'))

# =============================================================================
# LOGGING AYARLARI
# =============================================================================

LOG_FILE = os.getenv('LOG_FILE', 'telegram_messenger.log')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# =============================================================================
# FİLTRE AYARLARI
# =============================================================================

EXCLUDE_BOTS = os.getenv('EXCLUDE_BOTS', 'True').lower() == 'true'
EXCLUDE_ADMINS = os.getenv('EXCLUDE_ADMINS', 'True').lower() == 'true'
EXCLUDE_DELETED_ACCOUNTS = os.getenv('EXCLUDE_DELETED_ACCOUNTS', 'True').lower() == 'true'

# =============================================================================
# DEBUG AYARLARI
# =============================================================================

DEBUG_MODE = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
DRY_RUN = os.getenv('DRY_RUN', 'False').lower() == 'true'
RESET_DATA = os.getenv('RESET_DATA', 'False').lower() == 'true'

# =============================================================================
# GÜVENLİK ve PERFORMANS
# =============================================================================

MIN_USER_ID = int(os.getenv('MIN_USER_ID', '1'))
MAX_USER_ID = int(os.getenv('MAX_USER_ID', '9999999999999999999'))
ENABLE_ENTITY_CACHE = os.getenv('ENABLE_ENTITY_CACHE', 'True').lower() == 'true'
CACHE_EXPIRE_TIME = int(os.getenv('CACHE_EXPIRE_TIME', '3600'))
ENABLE_MESSAGE_QUEUING = os.getenv('ENABLE_MESSAGE_QUEUING', 'True').lower() == 'true'
QUEUE_SIZE = int(os.getenv('QUEUE_SIZE', '100'))
ENABLE_ADAPTIVE_DELAY = os.getenv('ENABLE_ADAPTIVE_DELAY', 'True').lower() == 'true'
FLOOD_WAIT_MULTIPLIER = float(os.getenv('FLOOD_WAIT_MULTIPLIER', '1.5'))

# =============================================================================
# DURUM RAPORU
# =============================================================================

FALLBACK_TO_CONSOLE = os.getenv('FALLBACK_TO_CONSOLE', 'True').lower() == 'true'
ENABLE_STATUS_LOGGING = os.getenv('ENABLE_STATUS_LOGGING', 'True').lower() == 'true'
MIN_STATUS_INTERVAL = int(os.getenv('MIN_STATUS_INTERVAL', '300'))
MAX_STATUS_PER_HOUR = int(os.getenv('MAX_STATUS_PER_HOUR', '12'))

# =============================================================================
# VALIDATION
# =============================================================================

def validate_config():
    """Konfigürasyonu doğrula"""
    errors = []

    if COLLECTOR_API_ID == 0:
        errors.append("COLLECTOR_API_ID ayarlanmamış")

    if not COLLECTOR_API_HASH:
        errors.append("COLLECTOR_API_HASH ayarlanmamış")

    if STATUS_USER_ID == 0:
        errors.append("STATUS_USER_ID ayarlanmamış")

    if not SENDER_ACCOUNTS:
        errors.append("Hiç sender hesabı tanımlanmamış")

    if not DATABASE_URL:
        errors.append("DATABASE_URL ayarlanmamış")

    return errors

# Config validation
validation_errors = validate_config()
if validation_errors:
    print("⚠️ KONFİGÜRASYON HATALARI:")
    for error in validation_errors:
        print(f"   • {error}")
    if not DEBUG_MODE:
        print("   💡 .env dosyanızı kontrol edin")

print(f"✅ Config yüklendi:")
print(f"   📡 Collector: {COLLECTOR_API_ID}")
print(f"   📤 Sender sayısı: {len(SENDER_ACCOUNTS)}")
print(f"   🎯 İzlenen gruplar: {len(COLLECTOR_GROUPS)}")
print(f"   📊 Status User: {STATUS_USER_ID}")
print(f"   🗄️ Database: {'✅' if DATABASE_URL else '❌'}")
