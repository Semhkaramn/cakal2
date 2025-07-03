"""
Status Reporter - DÜZELTILMIŞ VERSİYON
Entity resolution sorunları çözülmüş
"""

import logging
import asyncio
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import FloodWaitError
import config

logger = logging.getLogger(__name__)

class StatusReporter:
    def __init__(self, client: TelegramClient):
        self.client = client
        self.status_user_id = config.STATUS_USER_ID
        self.last_report_time = None
        self.entity_cached = False

    async def send_status(self, message: str, force: bool = False) -> bool:
        """Status mesajı gönder - DÜZELTILMIŞ ENTITY RESOLUTION"""
        try:
            if not self.status_user_id:
                logger.info("📢 Status User ID ayarlanmamış, mesaj konsola yazılıyor")
                print(f"\n=== STATUS MESSAGE ===\n{message}\n=====================\n")
                return False

            # Eğer force değilse ve son rapor çok yakın zamanda gönderildiyse atla
            if not force and self.last_report_time:
                time_diff = (datetime.now() - self.last_report_time).seconds
                if time_diff < 300:  # 5 dakika minimum aralık
                    return False

            # Timestamp ekle
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"🤖 **TELEGRAM MESSENGER STATUS** 🤖\n⏰ {timestamp}\n\n{message}"

            # DÜZELTILMIŞ: Entity resolution ile kullanıcıyı bul
            try:
                # Farklı yöntemlerle entity bulmayı dene
                entity = await self._resolve_status_user()

                if not entity:
                    # Entity bulunamazsa konsola yaz ve devam et
                    logger.warning(f"⚠️ Status user entity bulunamadı: {self.status_user_id}")
                    logger.info("💡 Mesaj konsola yazılıyor...")
                    print(f"\n=== STATUS MESSAGE ===\n{formatted_message}\n=====================\n")
                    return False

            except Exception as e:
                logger.warning(f"⚠️ Status user entity çözümlenemedi: {self.status_user_id} - {str(e)}")
                logger.info("💡 Bu durumda status mesajları konsola yazılacak")
                print(f"\n=== STATUS MESSAGE ===\n{formatted_message}\n=====================\n")
                return False

            # Mesajı gönder
            await self.client.send_message(entity, formatted_message)
            self.last_report_time = datetime.now()

            logger.info(f"✅ Status mesajı gönderildi: {self.status_user_id}")
            return True

        except FloodWaitError as e:
            logger.warning(f"⏳ Status mesajı flood wait: {e.seconds}s")
            return False
        except Exception as e:
            if "USER_NOT_FOUND" in str(e) or "not found" in str(e).lower():
                logger.error(f"❌ Status kullanıcısı bulunamadı: {self.status_user_id}")
            elif "Could not find the input entity" in str(e):
                logger.warning(f"⚠️ Status user entity çözümlenemedi: {self.status_user_id}")
                logger.info("💡 Bu durumda status mesajları konsola yazılacak")
                print(f"\n=== STATUS MESSAGE ===\n{message}\n=====================\n")
            else:
                logger.error(f"❌ Status mesajı hatası: {str(e)}")
            return False

    async def _resolve_status_user(self):
        """Status user entity'sini çöz - ÇEŞİTLİ YÖNTEMLERLE"""
        try:
            # Yöntem 1: Direkt user ID ile
            try:
                entity = await self.client.get_entity(self.status_user_id)
                logger.debug(f"✅ Entity bulundu (user_id): {self.status_user_id}")
                return entity
            except ValueError:
                pass  # Devam et

            # Yöntem 2: Dialogs'dan ara
            try:
                async for dialog in self.client.iter_dialogs():
                    if hasattr(dialog.entity, 'id') and dialog.entity.id == self.status_user_id:
                        logger.debug(f"✅ Entity bulundu (dialogs): {self.status_user_id}")
                        return dialog.entity
            except Exception:
                pass

            # Yöntem 3: Eğer username varsa onunla dene (config'de eklenebilir)
            if hasattr(config, 'STATUS_USERNAME') and config.STATUS_USERNAME:
                try:
                    entity = await self.client.get_entity(config.STATUS_USERNAME)
                    if entity.id == self.status_user_id:
                        logger.debug(f"✅ Entity bulundu (username): {config.STATUS_USERNAME}")
                        return entity
                except Exception:
                    pass

            # Hiçbiri çalışmazsa None döndür
            return None

        except Exception as e:
            logger.debug(f"Entity resolution error: {e}")
            return None

    async def send_startup_status(self, active_accounts: int, monitoring_groups: list):
        """Başlangıç durumu mesajı"""
        message = f"""🚀 **SİSTEM BAŞLATILDI**

📱 **Aktif Hesaplar:** {active_accounts}
📡 **İzlenen Gruplar:** {len(monitoring_groups)}
{chr(10).join([f"   • {group}" for group in monitoring_groups[:5]])}
{"   • ..." if len(monitoring_groups) > 5 else ""}

🗄️ **Database:** Heroku PostgreSQL aktif
⚙️ **Mód:** Otomatik çalışma modu
✅ **Durum:** Sistem hazır ve çalışıyor!

📊 Durum raporları {config.STATUS_INTERVAL//60} dakikada bir gelecek.
🎮 Komutlar için /yardim yazın."""

        await self.send_status(message, force=True)

    async def send_collector_status(self, stats: dict):
        """Collector durum mesajı"""
        message = f"""📡 **COLLECTOR RAPORU**

👥 **Toplanan Kullanıcılar:**
   • Aktif üyeler: {stats.get('active_members', 0)}
   • Toplam benzersiz: {stats.get('total_unique_members', 0)}

📊 **Bu Oturumda:**
   • Yeni toplanan: {stats.get('session_collected', 0)}
   • Son toplama: {stats.get('last_collection_time', 'N/A')}

🎯 **Hedef Durumu:**
   • Kalan hedef: {stats.get('remaining_members', 0)}
   • Gönderilen mesaj: {stats.get('sent_messages', 0)}"""

        await self.send_status(message)

    async def send_sender_status(self, stats: dict):
        """Sender durum mesajı"""
        message = f"""📤 **SENDER RAPORU**

📊 **Bu Oturumda:**
   • Gönderilen: {stats.get('session_sent', 0)}
   • Başarısız: {stats.get('session_failed', 0)}
   • Başarı oranı: {stats.get('success_rate', 0)}%

🎯 **Toplam Durum:**
   • Toplam gönderilen: {stats.get('total_sent_db', 0)}
   • Kalan hedef: {stats.get('remaining_targets', 0)}
   • Aktif hesap: {stats.get('active_accounts', 0)}

⏱️ **Tahmini Süre:**
   • Kalan süre: {stats.get('estimated_time', 'Hesaplanıyor...')}"""

        await self.send_status(message)

    async def send_error_status(self, error_type: str, error_message: str):
        """Hata durumu mesajı"""
        message = f"""⚠️ **HATA RAPORU**

🔴 **Hata Tipi:** {error_type}
📝 **Detay:** {error_message}
⏰ **Zaman:** {datetime.now().strftime('%H:%M:%S')}

🔄 Sistem hata yönetimi devreye girdi.
✅ Diğer hesaplar çalışmaya devam ediyor."""

        await self.send_status(message, force=True)

    async def send_completion_status(self, final_stats: dict):
        """Tamamlanma durumu mesajı"""
        message = f"""🎯 **İŞLEM TAMAMLANDI**

📊 **FINAL SONUÇLAR:**
   • Toplam gönderilen: {final_stats.get('total_sent', 0)}
   • Başarısız: {final_stats.get('total_failed', 0)}
   • Başarı oranı: {final_stats.get('success_rate', 0)}%

⏱️ **Süre Bilgisi:**
   • Başlangıç: {final_stats.get('start_time', 'N/A')}
   • Bitiş: {datetime.now().strftime('%H:%M:%S')}
   • Toplam süre: {final_stats.get('duration', 'N/A')}

✅ Tüm işlemler tamamlandı!"""

        await self.send_status(message, force=True)

    async def send_daily_summary(self, daily_stats: dict):
        """Günlük özet mesajı"""
        message = f"""📅 **GÜNLÜK ÖZET**

📊 **Bugün Toplanan:**
   • Yeni aktif üye: {daily_stats.get('new_members_today', 0)}
   • Güncellenen üye: {daily_stats.get('updated_members_today', 0)}

📤 **Bugün Gönderilen:**
   • Mesaj sayısı: {daily_stats.get('messages_today', 0)}
   • Başarı oranı: {daily_stats.get('success_rate_today', 0)}%

💾 **Veritabanı:**
   • Toplam aktif üye: {daily_stats.get('total_active_members', 0)}
   • Kalan hedef: {daily_stats.get('remaining_targets', 0)}"""

        await self.send_status(message, force=True)

    async def send_command_response(self, command: str, result: str):
        """Komut sonucu mesajı"""
        message = f"""⚡ **KOMUT SONUCU**

📝 **Komut:** {command}
✅ **Sonuç:** {result}
⏰ **Zaman:** {datetime.now().strftime('%H:%M:%S')}"""

        await self.send_status(message, force=True)

    async def send_reset_confirmation(self, reset_type: str):
        """Reset onay mesajı"""
        message = f"""🗑️ **VERİ TEMİZLİĞİ**

🔄 **Temizlenen:** {reset_type}
✅ **Durum:** Başarıyla temizlendi
⏰ **Zaman:** {datetime.now().strftime('%H:%M:%S')}

🚀 Sistem yeniden başlatılıyor..."""

        await self.send_status(message, force=True)

    def format_time_duration(self, seconds: int) -> str:
        """Süreyi formatla"""
        if seconds < 60:
            return f"{seconds} saniye"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"{minutes} dakika"
        else:
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            return f"{hours} saat {minutes} dakika"

    def calculate_success_rate(self, sent: int, failed: int) -> int:
        """Başarı oranını hesapla"""
        total = sent + failed
        if total == 0:
            return 0
        return int((sent / total) * 100)

    async def setup_status_user(self):
        """Status user ile iletişim kurmak için yardımcı fonksiyon"""
        try:
            # Test mesajı gönder
            test_message = "🧪 Test mesajı - Telegram Messenger sistemi test ediliyor"
            success = await self.send_status(test_message, force=True)

            if success:
                logger.info("✅ Status user ile iletişim kuruldu!")
            else:
                logger.warning("⚠️ Status user ile iletişim kurulamadı")
                logger.info("💡 Çözüm: Status user ile önce manuel mesaj gönderin")

            return success

        except Exception as e:
            logger.error(f"❌ Status user setup hatası: {e}")
            return False
