"""
Telegram Komut Yöneticisi - DÜZELTILMIŞ VERSİYON
Telegram'dan gelen komutları işler ve sistemi kontrol eder
"""

import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, Union
from telethon import TelegramClient, events
from telethon.tl.types import User
from telethon.errors import FloodWaitError, RPCError
import config

logger = logging.getLogger(__name__)

class CommandHandler:
    def __init__(self, app_instance, status_reporter):
        self.app = app_instance
        self.status_reporter = status_reporter
        self.authorized_user_id = config.STATUS_USER_ID
        self.command_client: Optional[TelegramClient] = None
        self.is_listening = False

        # Sistem durumları
        self.system_states = {
            'collecting_enabled': True,
            'sending_enabled': True,
            'system_running': True,
            'auto_mode': True
        }

        # Komut istatistikleri
        self.command_stats = {
            'total_commands': 0,
            'successful_commands': 0,
            'failed_commands': 0,
            'last_command_time': None
        }

    async def setup_command_listener(self, client: TelegramClient):
        """Komut dinleyicisini kur"""
        try:
            if not client:
                logger.error("❌ Client sağlanmadı")
                return False

            self.command_client = client

            # Komut event handler'ı kur
            @client.on(events.NewMessage(pattern=r'^/\w+', from_users=[self.authorized_user_id]))
            async def command_handler(event):
                try:
                    await self.process_command(event)
                except Exception as e:
                    logger.error(f"❌ Komut handler hatası: {str(e)}")

            self.is_listening = True
            logger.info(f"🎮 Komut dinleyicisi kuruldu - Yetkili: {self.authorized_user_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Komut dinleyicisi kurulamadı: {str(e)}")
            return False

    async def process_command(self, event):
        """Komut işle"""
        try:
            command_text = event.raw_text.strip()
            user_id = event.sender_id

            logger.info(f"📟 Komut alındı: {command_text} - User: {user_id}")

            # İstatistikleri güncelle
            self.command_stats['total_commands'] += 1
            self.command_stats['last_command_time'] = datetime.now()

            # Yetki kontrolü
            if not self._is_authorized_user(user_id):
                await self._safe_respond(event, "❌ Bu komutu kullanma yetkiniz yok!")
                self.command_stats['failed_commands'] += 1
                return

            # Komutları işle
            response = await self.execute_command(command_text.lower())

            if response:
                success = await self._safe_respond(event, response)
                if success:
                    self.command_stats['successful_commands'] += 1
                else:
                    self.command_stats['failed_commands'] += 1
            else:
                self.command_stats['failed_commands'] += 1

        except Exception as e:
            logger.error(f"❌ Komut işleme hatası: {str(e)}")
            self.command_stats['failed_commands'] += 1
            try:
                await self._safe_respond(event, f"❌ Komut işlenirken hata: {str(e)[:100]}")
            except:
                logger.error("❌ Hata mesajı bile gönderilemedi")

    def _is_authorized_user(self, user_id: int) -> bool:
        """Kullanıcı yetkili mi kontrol et"""
        return user_id == self.authorized_user_id

    async def _safe_respond(self, event, message: str) -> bool:
        """Güvenli mesaj gönderimi"""
        try:
            # Mesaj uzunluğunu kontrol et (Telegram limiti)
            if len(message) > 4096:
                message = message[:4093] + "..."

            await event.respond(message)
            return True

        except FloodWaitError as e:
            logger.warning(f"⏳ Komut cevabı flood wait: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            try:
                await event.respond(message)
                return True
            except:
                return False

        except OSError as e:
            logger.error(f"❌ Bağlantı hatası komut cevabında: {str(e)}")
            return False

        except Exception as e:
            logger.error(f"❌ Komut cevap hatası: {str(e)}")
            return False

    async def execute_command(self, command: str) -> Optional[str]:
        """Komutları çalıştır"""
        try:
            command = command.strip().lower()

            # Komut mapping
            command_map = {
                '/yardim': self.get_help_text,
                '/start': self.get_help_text,
                '/durum': self.get_status_info,
                '/istatistik': self.get_detailed_stats,
                '/toplamayidurdur': self.pause_collecting,
                '/toplamabaslat': self.resume_collecting,
                '/gonderimidurdur': self.pause_sending,
                '/gonderimbaslat': self.resume_sending,
                '/sistemidurdur': self.stop_system,
                '/sistemibaslat': self.start_system,
                '/veritemizle': self.reset_data,
                '/mesajtemizle': self.reset_messages,
                '/veritabani': self.get_database_info,
                '/hesaplar': self.get_account_stats,
                '/yeniden': self.restart_system,
                '/tamtemizlik': self.full_cleanup
            }

            # Mesaj değiştirme komutu özel işlem gerektirir
            if command.startswith('/mesajdegistir'):
                return await self.set_custom_message(command)

            # Standart komutları çalıştır
            if command in command_map:
                handler = command_map[command]
                if asyncio.iscoroutinefunction(handler):
                    return await handler()
                else:
                    return handler()

            # Bilinmeyen komut
            return f"❌ Bilinmeyen komut: {command}\n\n{self.get_help_text()}"

        except Exception as e:
            logger.error(f"❌ Komut çalıştırma hatası: {str(e)}")
            return f"❌ Komut çalıştırma hatası: {str(e)[:100]}"

    def get_help_text(self) -> str:
        """Yardım metni"""
        return """🎮 **TELEGRAM MESSENGER TÜRKÇE KOMUTLARI**

**📊 BİLGİ KOMUTLARI:**
/durum - Sistem durumu
/istatistik - Detaylı istatistikler
/hesaplar - Hesap durumları
/veritabani - Heroku PostgreSQL bilgisi

**⏯️ KONTROL KOMUTLARI:**
/toplamayidurdur - Veri toplamayı durdur
/toplamabaslat - Veri toplamayı başlat
/gonderimidurdur - Mesaj gönderimi durdur
/gonderimbaslat - Mesaj gönderimi başlat

**🔄 SİSTEM KOMUTLARI:**
/sistemidurdur - Sistemi tamamen durdur
/sistemibaslat - Sistemi başlat
/yeniden - Sistemi yeniden başlat

**🗑️ TEMİZLEME KOMUTLARI:**
/veritemizle - Tüm verileri sıfırla
/mesajtemizle - Sadece mesaj kayıtlarını sıfırla
/tamtemizlik - Tüm sistem ve verileri temizle

**⚙️ AYAR KOMUTLARI:**
/mesajdegistir [mesaj] - Mesaj metnini değiştir

**❓ YARDIM:**
/yardim - Bu yardım menüsü

🗄️ **Tüm veriler Heroku PostgreSQL'de güvenle saklanır**
🎯 **Sistem SADECE ANLIK mesaj atanları toplar**
📡 **Geçmiş tarama YOK - Sadece canlı dinleme**"""

    async def get_status_info(self) -> str:
        """Durum bilgisi"""
        try:
            runtime = datetime.now() - self.app.start_time
            hours = runtime.seconds // 3600
            minutes = (runtime.seconds % 3600) // 60

            status_icons = {
                'system_running': '🟢' if self.system_states['system_running'] else '🔴',
                'collecting': '🟢' if self.system_states['collecting_enabled'] else '🔴',
                'sending': '🟢' if self.system_states['sending_enabled'] else '🔴'
            }

            db_stats = self.app.db.get_session_stats()

            return f"""📊 **SİSTEM DURUMU**

**🔧 Sistem Durumu:**
{status_icons['system_running']} Sistem: {'ÇALIŞIYOR' if self.system_states['system_running'] else 'DURDURULDU'}
{status_icons['collecting']} Veri Toplama: {'AKTİF' if self.system_states['collecting_enabled'] else 'DURDURULDU'}
{status_icons['sending']} Mesaj Gönderimi: {'AKTİF' if self.system_states['sending_enabled'] else 'DURDURULDU'}

**⏱️ Çalışma Süresi:** {hours} saat {minutes} dakika

**👥 Kullanıcı Sayıları:**
• Aktif üyeler: {db_stats.get('active_members', 0):,}
• Toplam benzersiz: {db_stats.get('total_unique_members', 0):,}
• Kalan hedef: {db_stats.get('remaining_members', 0):,}

**📤 Mesaj Durumu:**
• Toplam gönderilen: {db_stats.get('sent_messages', 0):,}
• Bu oturumda: {getattr(self.app, 'session_stats', {}).get('sent_messages', 0):,}

**🎯 Günlük Özet:**
• Bugün toplanan: {db_stats.get('new_members_today', 0):,}
• Bugün gönderilen: {db_stats.get('messages_today', 0):,}"""

        except Exception as e:
            logger.error(f"❌ Status info hatası: {e}")
            return f"❌ Durum bilgisi alınamadı: {str(e)[:100]}"

    async def get_detailed_stats(self) -> str:
        """Detaylı istatistikler"""
        try:
            db_stats = self.app.db.get_session_stats()
            account_stats = self.app.account_manager.get_account_stats()

            account_list = []
            for acc in account_stats.get('accounts', []):
                role = acc.get('role', 'unknown')
                status = '🟢' if acc.get('is_active') else '🔴'
                phone = acc.get('phone', 'N/A')
                msg_count = acc.get('message_count', 0)
                account_list.append(f"{status} {phone} ({role}) - {msg_count} mesaj")

            account_text = '\n'.join(account_list[:10])  # İlk 10 hesap
            if len(account_list) > 10:
                account_text += f"\n... ve {len(account_list) - 10} hesap daha"

            return f"""📈 **DETAYLI İSTATİSTİKLER**

**📱 Hesap Durumları:**
{account_text or 'Hesap bulunamadı'}

**📊 Veritabanı:**
• Aktif üyeler: {db_stats.get('active_members', 0):,}
• Static üyeler: {db_stats.get('static_members', 0):,}
• Toplam benzersiz: {db_stats.get('total_unique_members', 0):,}
• Kalan aktif hedef: {db_stats.get('remaining_active_members', 0):,}
• Kalan static hedef: {db_stats.get('remaining_static_members', 0):,}

**📤 Mesaj İstatistikleri:**
• Toplam başarılı: {db_stats.get('sent_messages', 0):,}
• Bugün gönderilen: {db_stats.get('messages_today', 0):,}
• Bugün başarısız: {db_stats.get('failed_today', 0):,}
• Bugün başarı oranı: {db_stats.get('success_rate_today', 100)}%

**⚙️ Sistem Ayarları:**
• Mesaj metni: {config.BASE_MESSAGE[:50]}...
• Bekleme süresi: {config.MESSAGE_DELAY_MIN}-{config.MESSAGE_DELAY_MAX}s
• Saatlik limit: {config.MESSAGES_PER_HOUR}
• Collector grupları: {len(config.COLLECTOR_GROUPS)}

**🎮 Komut İstatistikleri:**
• Toplam komut: {self.command_stats['total_commands']}
• Başarılı: {self.command_stats['successful_commands']}
• Başarısız: {self.command_stats['failed_commands']}"""

        except Exception as e:
            logger.error(f"❌ Detailed stats hatası: {e}")
            return f"❌ Detaylı istatistik alınamadı: {str(e)[:100]}"

    async def pause_collecting(self) -> str:
        """Veri toplamayı durdur"""
        try:
            self.system_states['collecting_enabled'] = False
            logger.info("⏸️ Veri toplama durduruldu")
            return "⏸️ **VERİ TOPLAMA DURDURULDU**\n\nMesaj gönderimi devam ediyor.\nBaşlatmak için: /toplamabaslat"
        except Exception as e:
            return f"❌ Veri toplama durdurma hatası: {str(e)}"

    async def resume_collecting(self) -> str:
        """Veri toplamayı başlat"""
        try:
            self.system_states['collecting_enabled'] = True
            logger.info("▶️ Veri toplama başlatıldı")
            return "▶️ **VERİ TOPLAMA BAŞLATILDI**\n\nSistem aktif kullanıcıları toplamaya devam ediyor."
        except Exception as e:
            return f"❌ Veri toplama başlatma hatası: {str(e)}"

    async def pause_sending(self) -> str:
        """Mesaj gönderimi durdur"""
        try:
            self.system_states['sending_enabled'] = False
            logger.info("⏸️ Mesaj gönderimi durduruldu")
            return "⏸️ **MESAJ GÖNDERİMİ DURDURULDU**\n\n✅ Devam eden gönderimler durduruldu\n📡 Canlı mesaj dinleme devam ediyor\n▶️ Başlatmak için: /gonderimbaslat"
        except Exception as e:
            return f"❌ Mesaj gönderimi durdurma hatası: {str(e)}"

    async def resume_sending(self) -> str:
        """Mesaj gönderimi başlat"""
        try:
            self.system_states['sending_enabled'] = True
            logger.info("▶️ Mesaj gönderimi başlatıldı")
            return "▶️ **MESAJ GÖNDERİMİ BAŞLATILDI**\n\n✅ Sistem mesaj göndermeye devam ediyor\n📡 Canlı toplanan üyelere mesaj gönderilecek"
        except Exception as e:
            return f"❌ Mesaj gönderimi başlatma hatası: {str(e)}"

    async def stop_system(self) -> str:
        """Sistemi durdur"""
        try:
            self.system_states['system_running'] = False
            self.system_states['collecting_enabled'] = False
            self.system_states['sending_enabled'] = False
            logger.info("🛑 Sistem tamamen durduruldu")
            return "🛑 **SİSTEM TAMAMEN DURDURULDU**\n\n❌ Tüm işlemler durduruldu\n❌ Canlı dinleme durdu\n❌ Mesaj gönderimi durdu\n▶️ Başlatmak için: /sistemibaslat"
        except Exception as e:
            return f"❌ Sistem durdurma hatası: {str(e)}"

    async def start_system(self) -> str:
        """Sistemi başlat"""
        try:
            self.system_states['system_running'] = True
            self.system_states['collecting_enabled'] = True
            self.system_states['sending_enabled'] = True
            logger.info("🚀 Sistem başlatıldı")
            return "🚀 **SİSTEM BAŞLATILDI**\n\nTüm işlemler aktif!"
        except Exception as e:
            return f"❌ Sistem başlatma hatası: {str(e)}"

    async def reset_data(self) -> str:
        """Tüm verileri sıfırla"""
        try:
            self.app.db.reset_all_data()
            logger.info("🗑️ Tüm veriler sıfırlandı")
            return "🗑️ **TÜM VERİLER SIFIRLANDI**\n\n• Toplanan kullanıcılar silindi\n• Mesaj kayıtları silindi\n• Sistem sıfırdan başlayacak"
        except Exception as e:
            return f"❌ Veri sıfırlama hatası: {str(e)}"

    async def reset_messages(self) -> str:
        """Sadece mesaj kayıtlarını sıfırla"""
        try:
            self.app.db.reset_sent_messages_only()
            logger.info("🗑️ Mesaj kayıtları sıfırlandı")
            return "🗑️ **MESAJ KAYITLARI SIFIRLANDI**\n\nToplanan kullanıcılara yeniden mesaj gönderilebilir."
        except Exception as e:
            return f"❌ Mesaj sıfırlama hatası: {str(e)}"

    async def set_custom_message(self, command: str) -> str:
        """Mesaj metnini değiştir"""
        try:
            # /mesajdegistir sonrasındaki metni al
            parts = command.split(' ', 1)
            if len(parts) < 2:
                return "❌ Kullanım: /mesajdegistir [yeni mesaj metni]"

            new_message = parts[1].strip()
            if not new_message:
                return "❌ Boş mesaj metni girilemez"

            if len(new_message) > 500:
                return "❌ Mesaj metni çok uzun (max 500 karakter)"

            # Global config'i güncelle
            config.BASE_MESSAGE = new_message

            logger.info(f"📝 Mesaj metni değiştirildi: {new_message}")
            return f"✅ **MESAJ METNİ DEĞİŞTİRİLDİ**\n\nYeni mesaj: {new_message}"

        except Exception as e:
            return f"❌ Mesaj değiştirme hatası: {str(e)}"

    async def get_account_stats(self) -> str:
        """Hesap istatistikleri"""
        try:
            account_stats = self.app.account_manager.get_account_stats()

            collector_accounts = []
            sender_accounts = []

            for acc in account_stats.get('accounts', []):
                role = acc.get('role', 'unknown')
                status = '🟢 AKTİF' if acc.get('is_active') else '🔴 DEAKTİF'
                phone = acc.get('phone', 'N/A')
                name = acc.get('name', 'N/A')
                msg_count = acc.get('message_count', 0)

                account_info = f"{status}\n📞 {phone}\n👤 {name}\n📤 {msg_count} mesaj"

                if role == 'collector':
                    collector_accounts.append(account_info)
                else:
                    sender_accounts.append(account_info)

            result = "📱 **HESAP DURUMU**\n\n"

            if collector_accounts:
                result += "📡 **COLLECTOR HESABI:**\n"
                result += "\n".join(collector_accounts) + "\n\n"

            if sender_accounts:
                result += "📤 **SENDER HESAPLARI:**\n"
                for i, acc in enumerate(sender_accounts, 1):
                    result += f"**Sender {i}:**\n{acc}\n\n"

            if not collector_accounts and not sender_accounts:
                result += "❌ Aktif hesap bulunamadı"

            return result

        except Exception as e:
            return f"❌ Hesap istatistikleri alınamadı: {str(e)}"

    async def get_database_info(self) -> str:
        """Heroku PostgreSQL bilgilerini getir"""
        try:
            db_info = self.app.db.get_heroku_database_info()

            if not db_info:
                return "❌ **DATABASE BİLGİSİ ALINAMADI**\n\nPostgreSQL bağlantısı kontrol edin."

            table_info = ""
            for table, count in db_info.get('table_counts', {}).items():
                table_info += f"• {table}: {count:,} kayıt\n"

            version_short = db_info.get('version', 'Bilinmiyor')[:100]
            size = db_info.get('database_size', 'Bilinmiyor')

            return f"""🗄️ **HEROKU POSTGRESQL BİLGİSİ**

📊 **Database:**
• Boyut: {size}
• Versiyon: {version_short}

📋 **Tablo Durumu:**
{table_info or 'Tablo bilgisi bulunamadı'}

✅ **Durum:** Heroku PostgreSQL aktif ve çalışıyor"""

        except Exception as e:
            return f"❌ **DATABASE BİLGİSİ HATASI**\n\n{str(e)[:200]}"

    async def restart_system(self) -> str:
        """Sistemi yeniden başlat"""
        try:
            # Önce durdur
            self.system_states['system_running'] = False
            self.system_states['collecting_enabled'] = False
            self.system_states['sending_enabled'] = False

            await asyncio.sleep(2)  # Kısa bekleme

            # Sonra başlat
            self.system_states['system_running'] = True
            self.system_states['collecting_enabled'] = True
            self.system_states['sending_enabled'] = True

            logger.info("🔄 Sistem yeniden başlatıldı")
            return "🔄 **SİSTEM YENİDEN BAŞLATILDI**\n\nTüm işlemler yeniden başlatıldı."
        except Exception as e:
            return f"❌ Sistem yeniden başlatma hatası: {str(e)}"

    async def full_cleanup(self) -> str:
        """Tüm verileri ve sistemleri temizle"""
        try:
            # Verileri temizle
            self.app.db.reset_all_data()
            self.app.account_manager.reset_account_data()

            # İstatistikleri sıfırla
            self.command_stats = {
                'total_commands': 0,
                'successful_commands': 0,
                'failed_commands': 0,
                'last_command_time': None
            }

            logger.info("🗑️ Tüm veriler ve sistem temizlendi")
            return "🗑️ **TÜM VERİLER VE SİSTEM TEMİZLENDİ**\n\n• Toplanan kullanıcılar silindi\n• Mesaj kayıtları silindi\n• Hesap istatistikleri sıfırlandı\n• Komut istatistikleri sıfırlandı\n• Sistem sıfırdan başlayacak"
        except Exception as e:
            return f"❌ Tam temizlik hatası: {str(e)}"

    # Status checker methods
    def is_collecting_enabled(self) -> bool:
        """Veri toplama aktif mi?"""
        return self.system_states['collecting_enabled'] and self.system_states['system_running']

    def is_sending_enabled(self) -> bool:
        """Mesaj gönderimi aktif mi?"""
        return self.system_states['sending_enabled'] and self.system_states['system_running']

    def is_system_running(self) -> bool:
        """Sistem çalışıyor mu?"""
        return self.system_states['system_running']

    def get_system_states(self) -> Dict[str, bool]:
        """Sistem durumlarını getir"""
        return self.system_states.copy()

    def get_command_stats(self) -> Dict[str, Union[int, Optional[datetime]]]:
        """Komut istatistiklerini getir"""
        return self.command_stats.copy()
