"""
Telegram Mass Messenger Konfigürasyonu - DÜZELTILMIŞ VERSİYON
Tüm ayarlar hardcode - Environment variables kullanılmıyor
SADECE ANLIK MESAJ DINLEME MODU
"""

import os

# =============================================================================
# ANA HESAP BİLGİLERİ (HARDCODE)
# =============================================================================

# Collector hesap API ayarları
COLLECTOR_API_ID = 25846490
COLLECTOR_API_HASH = "63e7242d97fd985c2287a36a5355f100"
COLLECTOR_SESSION = "hesap1"

# İzlenecek gruplar
COLLECTOR_GROUPS = ["@CSSAGO"]

# Status raporu ayarları
STATUS_USER_ID = 5725763398
STATUS_USERNAME = None  # Eğer biliyorsanız buraya username ekleyin örn: "kullanici_adi"
STATUS_INTERVAL = 3600  # 1 saat

# Sender hesapları
SENDER_ACCOUNTS = [
    {
        'number': 1,
        'api_id': 22268590,
        'api_hash': "1e50437dc8deb030023ab1692ba40992",
        'session_name': "hesap2"
    }
    # Daha fazla sender eklemek için:
    # {
    #     'number': 2,
    #     'api_id': 33333333,
    #     'api_hash': "your_api_hash_2",
    #     'session_name': "hesap3"
    # }
]

# =============================================================================
# MESAJ AYARLARI
# =============================================================================

# Gönderilecek ana mesaj
BASE_MESSAGE = "MERHABA NASILSINIZ SAGO"

# Mesaj çeşitlendirme için ön ve son ekler
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
# RATE LIMITING AYARLARI (DAHA GÜVENLİ ve OPTİMİZE)
# =============================================================================

# Mesajlar arası bekleme süresi (saniye) - Optimized
MESSAGE_DELAY_MIN = 45  # 45 saniye minimum
MESSAGE_DELAY_MAX = 90  # 90 saniye maksimum

# Hesap değiştirme bekleme süresi (saniye)
ACCOUNT_SWITCH_DELAY = 15

# Batch işleme ayarları - Daha küçük batch'ler
BATCH_SIZE = 10
MESSAGES_PER_HOUR = 80  # Daha makul saatlik mesaj sayısı

# =============================================================================
# COLLECTOR AYARLARI (SADECE CANLI DİNLEME)
# =============================================================================

# ⚠️ GEÇMİŞ MESAJ TARAMA KAPALI
COLLECT_HISTORY_HOURS = 0  # Geçmiş tarama yok
COLLECT_LIMIT_PER_GROUP = 0  # Geçmiş limit yok

# Sadece canlı mesaj modu
LIVE_ONLY_MODE = True
SKIP_HISTORY_SCAN = True

# =============================================================================
# İŞ AKIŞI AYARLARI
# =============================================================================

# Çalışma modu: auto, collector, sender
WORK_MODE = "auto"

# Collection süresi (saniye) - Canlı dinleme için
AUTO_COLLECT_DURATION = 300  # 5 dakika check

# Sending süresi (saniye)
AUTO_SEND_DURATION = 1800  # 30 dakika

# =============================================================================
# VERİTABANI AYARLARI
# =============================================================================

# PostgreSQL bağlantısı (Heroku otomatik sağlar)
DATABASE_URL = os.getenv('DATABASE_URL')  # Bu Heroku'dan gelecek

# =============================================================================
# HATA YÖNETİMİ ve RETRY POLİTİKALARI
# =============================================================================

MAX_RETRIES = 3
RETRY_DELAY = 15  # Retry delay artırıldı

# Entity validation için
VALIDATE_ENTITIES = True
SKIP_INVALID_USERS = True

# Timeout ayarları
CONNECTION_TIMEOUT = 30
MESSAGE_TIMEOUT = 30

# =============================================================================
# LOGGING AYARLARI
# =============================================================================

LOG_FILE = "telegram_messenger.log"
LOG_LEVEL = "DEBUG"  # Daha az verbose

# =============================================================================
# FİLTRE AYARLARI
# =============================================================================

# Bot'ları hariç tut
EXCLUDE_BOTS = True

# Admin'leri hariç tut
EXCLUDE_ADMINS = True

# Silinmiş hesapları hariç tut
EXCLUDE_DELETED_ACCOUNTS = True

# =============================================================================
# DEBUG AYARLARI
# =============================================================================

DEBUG_MODE = False
DRY_RUN = False  # Test modu, gerçek mesaj gönderme

# Başlangıçta veriyi temizle
RESET_DATA = False

# =============================================================================
# GÜVENLİK ve PERFORMANS OPTİMİZASYONLARI
# =============================================================================

# ID doğrulama limitleri
MIN_USER_ID = 1
MAX_USER_ID = 9999999999999999999

# Entity cache ayarları
ENABLE_ENTITY_CACHE = True
CACHE_EXPIRE_TIME = 3600  # 1 saat

# Mesaj gönderim optimizasyonları
ENABLE_MESSAGE_QUEUING = True
QUEUE_SIZE = 100

# Flood control
ENABLE_ADAPTIVE_DELAY = True
FLOOD_WAIT_MULTIPLIER = 1.5

# =============================================================================
# DURUM RAPORU OPTİMİZASYONLARI
# =============================================================================

# Status mesajları için alternatif çözümler
FALLBACK_TO_CONSOLE = True  # Entity bulunamazsa konsola yaz
ENABLE_STATUS_LOGGING = True  # Status mesajlarını log'a da yaz

# Rapor sıklığı kontrolleri
MIN_STATUS_INTERVAL = 300  # 5 dakika minimum aralık
MAX_STATUS_PER_HOUR = 12   # Saatte max 12 status mesajı

# =============================================================================
# BAŞLATMA KONTROLÜ ve BİLGİLENDİRME
# =============================================================================

print(f"✅ DÜZELTILMIŞ Config yüklendi:")
print(f"   📡 Collector: {COLLECTOR_API_ID} -> {COLLECTOR_SESSION}")
print(f"   📤 Sender sayısı: {len(SENDER_ACCOUNTS)}")
print(f"   🎯 İzlenen gruplar: {len(COLLECTOR_GROUPS)}")
print(f"   📝 Mesaj: {BASE_MESSAGE[:30]}...")
print(f"   📊 Status User: {STATUS_USER_ID}")
print(f"   🎮 Türkçe komutlar: /yardim, /durum, /istatistik")
print(f"   🔴 MOD: SADECE CANLI MESAJ DİNLEME")
print(f"   ⚠️  Geçmiş tarama: KAPALI")
print(f"   📡 Canlı dinleme: AKTİF")
print(f"   🔧 SQL hatası: DÜZELTİLDİ")
print(f"   🚀 Entity resolution: İYİLEŞTİRİLDİ")
print(f"   ⚡ Optimizasyon: AKTİF")

# Kritik uyarılar
if not DATABASE_URL:
    print(f"   ⚠️  DATABASE_URL henüz set edilmemiş (Heroku'da otomatik gelecek)")

if STATUS_USER_ID:
    print(f"   💡 Status User: Önce {STATUS_USER_ID} ile manuel mesaj atın")

print(f"   📋 Düzeltilmiş dosyalar: database.py, status_reporter.py, message_sender.py")
print(f"   ✅ Sistem hazır!")

# =============================================================================
# HEROKU DİREKT KOMUTLARI (COPY-PASTE READY)
# =============================================================================

HEROKU_COMMANDS = f"""
# Heroku Config Commands (Copy-Paste Ready):
heroku config:set COLLECTOR_API_ID={COLLECTOR_API_ID}
heroku config:set COLLECTOR_API_HASH="{COLLECTOR_API_HASH}"
heroku config:set COLLECTOR_SESSION="{COLLECTOR_SESSION}"
heroku config:set COLLECTOR_GROUPS="{','.join(COLLECTOR_GROUPS)}"
heroku config:set STATUS_USER_ID={STATUS_USER_ID}
heroku config:set SENDER1_API_ID={SENDER_ACCOUNTS[0]['api_id']}
heroku config:set SENDER1_API_HASH="{SENDER_ACCOUNTS[0]['api_hash']}"
heroku config:set SENDER1_SESSION="{SENDER_ACCOUNTS[0]['session_name']}"
heroku config:set BASE_MESSAGE="{BASE_MESSAGE}"
heroku config:set WORK_MODE="{WORK_MODE}"

# Deployment Commands:
git add .
git commit -m "Fix SQL errors and entity resolution"
git push heroku main
heroku ps:scale worker=1
heroku logs --tail
"""

# Bu komutları daha sonra kullanmak için yazdır
if DEBUG_MODE:
    print("🔧 HEROKU DEPLOYMENT KOMUTLARI:")
    print(HEROKU_COMMANDS)
