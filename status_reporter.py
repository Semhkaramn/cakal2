"""
Status Reporter - DÜZELTILMIŞ VERSİYON
Entity resolution sorunları çözülmüş, hata yönetimi iyileştirilmiş
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Union, Any
from telethon import TelegramClient
from telethon.errors import FloodWaitError, UserNotFoundError, RPCError
import config

logger = logging.getLogger(__name__)

class StatusReporter:
    def __init__(self, client: TelegramClient):
        self.client = client
        self.status_user_id = config.STATUS_USER_ID
        self.last_report_time = None
        self.entity_cached = False
        self.status_entity = None
        self.fallback_mode = config.FALLBACK_TO_CONSOLE

    async def send_status(self, message: str, force: bool = False) -> bool:
        """Status mesajı gönder - DÜZELTILMIŞ ENTITY RESOLUTION"""
        try:
            if not self.status_user_id:
                logger.info("📢 Status User ID ayarlanmamış, mesaj konsola yazılıyor")
                self._print_to_console(message)
                return False

            # Rate limiting kontrolü
            if not force and self._is_rate_limited():
                return False

            # Timestamp ekle
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"🤖 **TELEGRAM MESSENGER STATUS** 🤖\n⏰ {timestamp}\n\n{message}"

            # Entity'yi çöz
            try:
                entity = await self._resolve_and_cache_status_user()

                if not entity:
                    if self.fallback_mode:
                        logger.info("💡 Entity bulunamadı, konsola yazılıyor...")
                        self._print_to_console(formatted_message)
                        return False
                    else:
                        logger.error(f"❌ Status user entity bulunamadı: {self.status_user_id}")
                        return False

            except Exception as e:
                if self.fallback_mode:
                    logger.warning(f"⚠️ Status user entity hatası: {str(e)} - konsola yazılıyor")
                    self._print_to_console(formatted_message)
                    return False
                else:
                    logger.error(f"❌ Status user entity çözümlenemedi: {str(e)}")
                    return False

            # Mesajı gönder
            await self.client.send_message(entity, formatted_message)
            self.last_report_time = datetime.now()

            logger.info(f"✅ Status mesajı gönderildi: {self.status_user_id}")

            # Ayrıca konsola da yaz (opsiyonel)
            if config.ENABLE_STATUS_LOGGING:
                self._print_to_console(formatted_message, prefix="[STATUS SENT]")

            return True

        except FloodWaitError as e:
            logger.warning(f"⏳ Status mesajı flood wait: {e.seconds}s")
            if self.fallback_mode:
                self._print_to_console(message, prefix="[FLOOD WAIT]")
            return False

        except Exception as e:
            error_msg = str(e)
            if any(keyword in error_msg.lower() for keyword in ['not found', 'user_not_found', 'could not find']):
                logger.error(f"❌ Status kullanıcısı bulunamadı: {self.status_user_id}")
                if self.fallback_mode:
                    self._print_to_console(message, prefix="[USER NOT FOUND]")
            else:
                logger.error(f"❌ Status mesajı hatası: {error_msg}")
                if self.fallback_mode:
                    self._print_to_console(message, prefix="[ERROR]")
            return False

    def _is_rate_limited(self) -> bool:
        """Rate limiting kontrolü"""
        if not self.last_report_time:
            return False

        time_diff = (datetime.now() - self.last_report_time).seconds
        return time_diff < config.MIN_STATUS_INTERVAL

    def _print_to_console(self, message: str, prefix: str = "[STATUS]"):
        """Konsola güvenli yazdırma"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"\n{prefix} {timestamp}")
            print("=" * 60)
            print(message)
            print("=" * 60)
            print()
        except Exception as e:
            logger.error(f"Konsol yazdırma hatası: {e}")

    async def _resolve_and_cache_status_user(self):
        """Status user entity'sini çöz ve cache'le"""
        try:
            # Eğer zaten cache'lenmiş ise kullan
            if self.status_entity and self.entity_cached:
                return self.status_entity

            # Farklı yöntemlerle entity bulmayı dene
            entity = await self._try_multiple_resolution_methods()

            if entity:
                self.status_entity = entity
                self.entity_cached = True
                logger.debug(f"✅ Status user entity cache'lendi: {self.status_user_id}")
                return entity

            return None

        except Exception as e:
            logger.debug(f"Entity cache hatası: {e}")
            return None

    async def _try_multiple_resolution_methods(self):
        """Farklı yöntemlerle entity çözme"""
        methods = [
            self._resolve_by_user_id,
            self._resolve_by_dialogs,
            self._resolve_by_username,
            self._resolve_by_contacts
        ]

        for method in methods:
            try:
                entity = await method()
                if entity:
                    logger.debug(f"✅ Entity bulundu: {method.__name__}")
                    return entity
            except Exception as e:
                logger.debug(f"{method.__name__} hatası: {e}")
                continue

        return None

    async def _resolve_by_user_id(self):
        """Direkt user ID ile çözme"""
        try:
            entity = await self.client.get_entity(self.status_user_id)
            if hasattr(entity, 'id') and entity.id == self.status_user_id:
                return entity
        except Exception:
            pass
        return None

    async def _resolve_by_dialogs(self):
        """Dialog'lardan arama"""
        try:
            async for dialog in self.client.iter_dialogs(limit=100):
                if hasattr(dialog.entity, 'id') and dialog.entity.id == self.status_user_id:
                    return dialog.entity
        except Exception:
            pass
        return None

    async def _resolve_by_username(self):
        """Username ile arama (eğer config'de varsa)"""
        try:
            if hasattr(config, 'STATUS_USERNAME') and config.STATUS_USERNAME:
                entity = await self.client.get_entity(config.STATUS_USERNAME)
                if hasattr(entity, 'id') and entity.id == self.status_user_id:
                    return entity
        except Exception:
            pass
        return None

    async def _resolve_by_contacts(self):
        """Kontaklar arasında arama"""
        try:
            async for user in self.client.iter_participants(self.client.get_input_entity('me')):
                if hasattr(user, 'id') and user.id == self.status_user_id:
                    return user
        except Exception:
            pass
        return None

    async def send_startup_status(self, active_accounts: int, monitoring_groups: list):
        """Başlangıç durumu mesajı"""
        group_list = '\n'.join([f"   • {group}" for group in monitoring_groups[:5]])
        if len(monitoring_groups) > 5:
            group_list += "\n   • ..."

        message = f"""🚀 **SİSTEM BAŞLATILDI**

📱 **Aktif Hesaplar:** {active_accounts}
📡 **İzlenen Gruplar:** {len(monitoring_groups)}
{group_list}

🗄️ **Database:** Heroku PostgreSQL aktif
⚙️ **Mod:** Otomatik çalışma modu
✅ **Durum:** Sistem hazır ve çalışıyor!

📊 Durum raporları {config.STATUS_INTERVAL//60} dakikada bir gelecek.
🎮 Komutlar için /yardim yazın."""

        await self.send_status(message, force=True)

    async def send_collector_status(self, stats: Dict[str, Union[int, str]]):
        """Collector durum mesajı"""
        message = f"""📡 **COLLECTOR RAPORU**

👥 **Toplanan Kullanıcılar:**
   • Aktif üyeler: {stats.get('active_members', 0):,}
   • Toplam benzersiz: {stats.get('total_unique_members', 0):,}

📊 **Bu Oturumda:**
   • Yeni toplanan: {stats.get('session_collected', 0):,}
   • Son toplama: {stats.get('last_collection_time', 'N/A')}

🎯 **Hedef Durumu:**
   • Kalan hedef: {stats.get('remaining_members', 0):,}
   • Gönderilen mesaj: {stats.get('sent_messages', 0):,}"""

        await self.send_status(message)

    async def send_sender_status(self, stats: Dict[str, Union[int, str]]):
        """Sender durum mesajı"""
        message = f"""📤 **SENDER RAPORU**

📊 **Bu Oturumda:**
   • Gönderilen: {stats.get('session_sent', 0):,}
   • Başarısız: {stats.get('session_failed', 0):,}
   • Başarı oranı: {stats.get('success_rate', 0)}%

🎯 **Toplam Durum:**
   • Toplam gönderilen: {stats.get('total_sent_db', 0):,}
   • Kalan hedef: {stats.get('remaining_targets', 0):,}
   • Aktif hesap: {stats.get('active_accounts', 0)}

⏱️ **Tahmini Süre:**
   • Kalan süre: {stats.get('estimated_time', 'Hesaplanıyor...')}"""

        await self.send_status(message)

    async def send_error_status(self, error_type: str, error_message: str):
        """Hata durumu mesajı"""
        # Uzun hata mesajlarını kısalt
        short_error = error_message[:200] + "..." if len(error_message) > 200 else error_message

        message = f"""⚠️ **HATA RAPORU**

🔴 **Hata Tipi:** {error_type}
📝 **Detay:** {short_error}
⏰ **Zaman:** {datetime.now().strftime('%H:%M:%S')}

🔄 Sistem hata yönetimi devreye girdi.
✅ Diğer hesaplar çalışmaya devam ediyor."""

        await self.send_status(message, force=True)

    async def send_completion_status(self, final_stats: Dict[str, Union[int, str]]):
        """Tamamlanma durumu mesajı"""
        success_rate = final_stats.get('success_rate', 0)

        message = f"""🎯 **İŞLEM TAMAMLANDI**

📊 **FINAL SONUÇLAR:**
   • Toplam gönderilen: {final_stats.get('total_sent', 0):,}
   • Başarısız: {final_stats.get('total_failed', 0):,}
   • Başarı oranı: {success_rate}%

⏱️ **Süre Bilgisi:**
   • Başlangıç: {final_stats.get('start_time', 'N/A')}
   • Bitiş: {datetime.now().strftime('%H:%M:%S')}
   • Toplam süre: {final_stats.get('duration', 'N/A')}

✅ Tüm işlemler tamamlandı!"""

        await self.send_status(message, force=True)

    async def send_daily_summary(self, daily_stats: Dict[str, Union[int, str]]):
        """Günlük özet mesajı"""
        message = f"""📅 **GÜNLÜK ÖZET**

📊 **Bugün Toplanan:**
   • Yeni aktif üye: {daily_stats.get('new_members_today', 0):,}
   • Güncellenen üye: {daily_stats.get('updated_members_today', 0):,}

📤 **Bugün Gönderilen:**
   • Mesaj sayısı: {daily_stats.get('messages_today', 0):,}
   • Başarı oranı: {daily_stats.get('success_rate_today', 0)}%

💾 **Veritabanı:**
   • Toplam aktif üye: {daily_stats.get('total_active_members', 0):,}
   • Kalan hedef: {daily_stats.get('remaining_targets', 0):,}"""

        await self.send_status(message, force=True)

    async def send_command_response(self, command: str, result: str):
        """Komut sonucu mesajı"""
        # Uzun sonuçları kısalt
        short_result = result[:300] + "..." if len(result) > 300 else result

        message = f"""⚡ **KOMUT SONUCU**

📝 **Komut:** {command}
✅ **Sonuç:** {short_result}
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

    def clear_entity_cache(self):
        """Entity cache'ini temizle"""
        self.status_entity = None
        self.entity_cached = False
        logger.debug("🗑️ Status entity cache temizlendi")

    async def test_status_connection(self) -> bool:
        """Status bağlantısını test et"""
        try:
            test_message = "🧪 Test mesajı - Telegram Messenger sistemi test ediliyor"
            success = await self.send_status(test_message, force=True)

            if success:
                logger.info("✅ Status user ile iletişim başarılı!")
                return True
            else:
                logger.warning("⚠️ Status user ile iletişim kurulamadı")
                if self.fallback_mode:
                    logger.info("💡 Fallback modu aktif - mesajlar konsola yazılacak")
                else:
                    logger.info("💡 Çözüm: Status user ile önce manuel mesaj gönderin")
                return False

        except Exception as e:
            logger.error(f"❌ Status test hatası: {e}")
            return False

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
            return 100
        return int((sent / total) * 100)

    async def setup_status_user(self) -> bool:
        """Status user kurulumu ve test"""
        try:
            logger.info(f"🔧 Status User kurulumu: {self.status_user_id}")

            # Entity cache'i temizle
            self.clear_entity_cache()

            # Test mesajı gönder
            success = await self.test_status_connection()

            return success

        except Exception as e:
            logger.error(f"❌ Status user setup hatası: {e}")
            return False
