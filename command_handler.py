"""
Telegram Komut Yöneticisi
Telegram'dan gelen komutları işler ve sistemi kontrol eder
"""

import logging
import asyncio
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import User
from telethon.errors import FloodWaitError
import config

logger = logging.getLogger(__name__)

class CommandHandler:
    def __init__(self, app_instance, status_reporter):
        self.app = app_instance
        self.status_reporter = status_reporter
        self.authorized_user_id = config.STATUS_USER_ID
        self.command_client = None
        self.is_listening = False

        # Sistem durumları
        self.system_states = {
            'collecting_enabled': True,
            'sending_enabled': True,
            'system_running': True,
            'auto_mode': True
        }

    async def setup_command_listener(self, client: TelegramClient):
        """Komut dinleyicisini kur"""
        try:
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

        except Exception as e:
            logger.error(f"❌ Komut dinleyicisi kurulamadı: {str(e)}")

    async def process_command(self, event):
        """Komut işle"""
        try:
            command_text = event.raw_text.strip().lower()
            user_id = event.sender_id

            logger.info(f"📟 Komut alındı: {command_text} - User: {user_id}")

            # Yetki kontrolü
            if user_id != self.authorized_user_id:
                await self._safe_respond(event, "❌ Bu komutu kullanma yetkiniz yok!")
                return

            # Komutları işle
            response = await self.execute_command(command_text)

            if response:
                await self._safe_respond(event, response)

        except Exception as e:
            logger.error(f"❌ Komut işleme hatası: {str(e)}")
            try:
                await self._safe_respond(event, f"❌ Komut işlenirken hata: {str(e)}")
            except:
                logger.error("❌ Hata mesajı bile gönderilemedi")

    async def _safe_respond(self, event, message: str):
        """Güvenli mesaj gönderimi"""
        try:
            await event.respond(message)
        except FloodWaitError as e:
            logger.warning(f"⏳ Komut cevabı flood wait: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            await event.respond(message)
        except OSError as e:
            logger.error(f"❌ Bağlantı hatası komut cevabında: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Komut cevap hatası: {str(e)}")

    async def execute_command(self, command: str) -> str:
        """Komutları çalıştır"""
        command = command.strip().lower()

        if command == '/yardim' or command == '/start':
            return self.get_help_text()

        elif command == '/durum':
            return await self.get_status_info()

        elif command == '/istatistik':
            return await self.get_detailed_stats()

        elif command == '/toplamayidurdur':
            return await self.pause_collecting()

        elif command == '/toplamabaslat':
            return await self.resume_collecting()

        elif command == '/gonderimidurdur':
            return await self.pause_sending()

        elif command == '/gonderimbaslat':
            return await self.resume_sending()

        elif command == '/sistemidurdur':
            return await self.stop_system()

        elif command == '/sistemibaslat':
            return await self.start_system()

        elif command == '/veritemizle':
            return await self.reset_data()

        elif command == '/mesajtemizle':
            return await self.reset_messages()

        elif command == '/veritabani':
            return await self.get_database_info()

        elif command.startswith('/mesajdegistir'):
            return await self.set_custom_message(command)

        elif command == '/hesaplar':
            return await self.get_account_stats()

        elif command == '/yeniden':
            return await self.restart_system()

        elif command == '/tamtemizlik':
            return await self.full_cleanup()

        else:
            return f"❌ Bilinmeyen komut: {command}\n\n{self.get_help_text()}"

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
• Aktif üyeler: {db_stats['active_members']}
• Toplam benzersiz: {db_stats['total_unique_members']}
• Kalan hedef: {db_stats['remaining_members']}

**📤 Mesaj Durumu:**
• Toplam gönderilen: {db_stats['sent_messages']}
• Bu oturumda: {self.app.session_stats['sent_messages']}

**🎯 Günlük Özet:**
• Bugün toplanan: {db_stats['new_members_today']}
• Bugün gönderilen: {db_stats['messages_today']}"""

    async def get_detailed_stats(self) -> str:
        """Detaylı istatistikler"""
        db_stats = self.app.db.get_session_stats()
        account_stats = self.app.account_manager.get_account_stats()

        account_list = []
        for acc in account_stats['accounts']:
            role = acc.get('role', 'unknown')
            status = '🟢' if acc['is_active'] else '🔴'
            account_list.append(f"{status} {acc['phone']} ({role}) - {acc['message_count']} mesaj")

        return f"""📈 **DETAYLI İSTATİSTİKLER**

**📱 Hesap Durumları:**
{chr(10).join(account_list)}

**📊 Veritabanı:**
• Aktif üyeler: {db_stats['active_members']}
• Static üyeler: {db_stats['static_members']}
• Toplam benzersiz: {db_stats['total_unique_members']}
• Kalan aktif hedef: {db_stats['remaining_active_members']}
• Kalan static hedef: {db_stats['remaining_static_members']}

**📤 Mesaj İstatistikleri:**
• Toplam başarılı: {db_stats['sent_messages']}
• Bugün gönderilen: {db_stats['messages_today']}
• Bugün başarısız: {db_stats['failed_today']}
• Bugün başarı oranı: {db_stats['success_rate_today']}%

**⚙️ Sistem Ayarları:**
• Mesaj metni: {config.BASE_MESSAGE[:50]}...
• Bekleme süresi: {config.MESSAGE_DELAY_MIN}-{config.MESSAGE_DELAY_MAX}s
• Saatlik limit: {config.MESSAGES_PER_HOUR}
• Collector grupları: {len(config.COLLECTOR_GROUPS)}"""

    async def pause_collecting(self) -> str:
        """Veri toplamayı durdur"""
        self.system_states['collecting_enabled'] = False
        logger.info("⏸️ Veri toplama durduruldu")
        return "⏸️ **VERİ TOPLAMA DURDURULDU**\n\nMesaj gönderimi devam ediyor.\nBaşlatmak için: /toplamabaslat"

    async def resume_collecting(self) -> str:
        """Veri toplamayı başlat"""
        self.system_states['collecting_enabled'] = True
        logger.info("▶️ Veri toplama başlatıldı")
        return "▶️ **VERİ TOPLAMA BAŞLATILDI**\n\nSistem aktif kullanıcıları toplamaya devam ediyor."

    async def pause_sending(self) -> str:
        """Mesaj gönderimi durdur"""
        self.system_states['sending_enabled'] = False
        logger.info("⏸️ Mesaj gönderimi durduruldu")

        # Aktif gönderim varsa bilgilendir
        return "⏸️ **MESAJ GÖNDERİMİ DURDURULDU**\n\n✅ Devam eden gönderimler durduruldu\n📡 Canlı mesaj dinleme devam ediyor\n▶️ Başlatmak için: /gonderimbaslat"

    async def resume_sending(self) -> str:
        """Mesaj gönderimi başlat"""
        self.system_states['sending_enabled'] = True
        logger.info("▶️ Mesaj gönderimi başlatıldı")
        return "▶️ **MESAJ GÖNDERİMİ BAŞLATILDI**\n\n✅ Sistem mesaj göndermeye devam ediyor\n📡 Canlı toplanan üyelere mesaj gönderilecek"

    async def stop_system(self) -> str:
        """Sistemi durdur"""
        self.system_states['system_running'] = False
        self.system_states['collecting_enabled'] = False
        self.system_states['sending_enabled'] = False
        logger.info("🛑 Sistem tamamen durduruldu")
        return "🛑 **SİSTEM TAMAMEN DURDURULDU**\n\n❌ Tüm işlemler durduruldu\n❌ Canlı dinleme durdu\n❌ Mesaj gönderimi durdu\n▶️ Başlatmak için: /sistemibaslat"

    async def start_system(self) -> str:
        """Sistemi başlat"""
        self.system_states['system_running'] = True
        self.system_states['collecting_enabled'] = True
        self.system_states['sending_enabled'] = True
        logger.info("🚀 Sistem başlatıldı")
        return "🚀 **SİSTEM BAŞLATILDI**\n\nTüm işlemler aktif!"

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

            new_message = parts[1]
            config.BASE_MESSAGE = new_message

            logger.info(f"📝 Mesaj metni değiştirildi: {new_message}")
            return f"✅ **MESAJ METNİ DEĞİŞTİRİLDİ**\n\nYeni mesaj: {new_message}"

        except Exception as e:
            return f"❌ Mesaj değiştirme hatası: {str(e)}"

    async def get_account_stats(self) -> str:
        """Hesap istatistikleri"""
        account_stats = self.app.account_manager.get_account_stats()

        collector_accounts = []
        sender_accounts = []

        for acc in account_stats['accounts']:
            role = acc.get('role', 'unknown')
            status = '🟢 AKTİF' if acc['is_active'] else '🔴 DEAKTİF'
            phone = acc['phone']
            name = acc['name']
            msg_count = acc['message_count']

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

        return result

    async def get_database_info(self) -> str:
        """Heroku PostgreSQL bilgilerini getir"""
        try:
            db_info = self.app.db.get_heroku_database_info()

            if not db_info:
                return "❌ **DATABASE BİLGİSİ ALINAMADI**\n\nPostgreSQL bağlantısı kontrol edin."

            table_info = ""
            for table, count in db_info.get('table_counts', {}).items():
                table_info += f"• {table}: {count:,} kayıt\n"

            return f"""🗄️ **HEROKU POSTGRESQL BİLGİSİ**

📊 **Database:**
• Boyut: {db_info.get('database_size', 'Bilinmiyor')}
• Versiyon: {db_info.get('version', 'Bilinmiyor')[:100]}

📋 **Tablo Durumu:**
{table_info}

✅ **Durum:** Heroku PostgreSQL aktif ve çalışıyor"""

        except Exception as e:
            return f"❌ **DATABASE BİLGİSİ HATASI**\n\n{str(e)}"

    def is_collecting_enabled(self) -> bool:
        """Veri toplama aktif mi?"""
        return self.system_states['collecting_enabled'] and self.system_states['system_running']

    def is_sending_enabled(self) -> bool:
        """Mesaj gönderimi aktif mi?"""
        return self.system_states['sending_enabled'] and self.system_states['system_running']

    def is_system_running(self) -> bool:
        """Sistem çalışıyor mu?"""
        return self.system_states['system_running']

    async def restart_system(self) -> str:
        """Sistemi yeniden başlat"""
        self.system_states['system_running'] = False
        self.system_states['collecting_enabled'] = False
        self.system_states['sending_enabled'] = False
        logger.info("🔄 Sistem yeniden başlatıldı")
        return "🔄 **SİSTEM YENİDEN BAŞLATILDI**\n\nTüm işlemler yeniden başlatıldı."

    async def full_cleanup(self) -> str:
        """Tüm verileri ve sistemleri temizle"""
        try:
            self.app.db.reset_all_data()
            self.app.account_manager.reset_account_data()
            logger.info("🗑️ Tüm veriler ve sistem temizlendi")
            return "🗑️ **TÜM VERİLER VE SİSTEM TEMİZLENDİ**\n\n• Toplanan kullanıcılar silindi\n• Mesaj kayıtları silindi\n• Sistem sıfırdan başlayacak"
        except Exception as e:
            return f"❌ Veri ve sistem temizleme hatası: {str(e)}"
