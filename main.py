"""
Telegram Mass Messenger - Ana Program
Tamamen otomatik çalışan sistem (Heroku için optimize)
"""

import asyncio
import logging
import sys
import os
import signal
from datetime import datetime, timedelta

# Kendi modüllerimizi import et
from database import DatabaseManager
from account_manager import AccountManager
from message_collector import MessageCollector
from message_sender import MessageSender
from group_scraper import GroupScraper
from status_reporter import StatusReporter
from command_handler import CommandHandler
import utils
import config

logger = logging.getLogger(__name__)

class TelegramMassMessenger:
    def __init__(self):
        logger.info("🚀 Telegram Mass Messenger başlatılıyor...")

        self.db = DatabaseManager()
        self.account_manager = AccountManager()
        self.collector = MessageCollector(self.db)
        self.sender = MessageSender(self.db, self.account_manager)
        self.scraper = GroupScraper(self.db)
        self.status_reporter = None
        self.command_handler = None
        self.running = False
        self.start_time = datetime.now()
        self.session_stats = {
            'collected_users': 0,
            'sent_messages': 0,
            'failed_messages': 0,
            'errors': []
        }

    async def initialize(self) -> bool:
        """Sistemi başlat"""
        logger.info("🚀 Sistem başlatılıyor...")

        # Veri sıfırlama kontrolü
        if config.RESET_DATA:
            logger.info("🗑️ Veri sıfırlama aktif - tüm veriler temizleniyor...")
            self.db.reset_all_data()

        # Session dosyalarını kontrol et
        session_files = utils.check_session_files()

        if not session_files:
            logger.error("❌ Session dosyası bulunamadı!")
            return False

        logger.info(f"📁 {len(session_files)} session dosyası bulundu")

        # Hesapları başlat
        logger.info("🔄 Hesaplar başlatılıyor...")
        success = await self.account_manager.initialize_clients()

        if not success:
            logger.error("❌ Hiç hesap başlatılamadı!")
            return False

        # Status reporter ve command handler'ı başlat (ilk hesabı kullan)
        if self.account_manager.active_accounts:
            first_account = self.account_manager.active_accounts[0]
            status_client = self.account_manager.get_active_client(first_account['session_name'])

            # Status reporter'ı başlat
            self.status_reporter = StatusReporter(status_client)

            # Command handler'ı başlat
            self.command_handler = CommandHandler(self, self.status_reporter)
            await self.command_handler.setup_command_listener(status_client)

            # ⭐ ÖNEMLİ: Message sender'a command handler referansını ver
            self.sender.set_command_handler(self.command_handler)

            # Başlangıç status mesajı gönder
            await self.status_reporter.send_startup_status(
                len(self.account_manager.active_accounts),
                config.COLLECTOR_GROUPS
            )

            # Komut menüsünü gönder
            help_text = self.command_handler.get_help_text()
            await self.status_reporter.send_status(f"🎮 **KOMUTLAR HAZIR**\n\n{help_text}", force=True)

        logger.info(f"✅ {len(self.account_manager.active_accounts)} hesap başarıyla başlatıldı")
        return True

    async def run_auto_mode(self):
        """Tamamen otomatik mod - Komutlarla kontrol edilebilir"""
        logger.info("🤖 Otomatik mod başlatılıyor...")

        try:
            # Collector'ı kur
            await self.setup_auto_collector()
            self.running = True

            while self.running:
                # Sistem durdurulmuşsa bekle
                if self.command_handler and not self.command_handler.is_system_running():
                    logger.info("⏸️ Sistem durduruldu, bekleniyor...")
                    await asyncio.sleep(30)
                    continue

                cycle_start = datetime.now()

                # 1. Collection fazı (eğer aktif ise)
                if not self.command_handler or self.command_handler.is_collecting_enabled():
                    logger.info("📡 Collection fazı başlatılıyor...")
                    collection_stats = await self.run_auto_collection()

                    if self.status_reporter:
                        await self.status_reporter.send_collector_status(collection_stats)
                else:
                    logger.info("⏸️ Collection deaktif, atlanıyor...")

                # 2. Sending fazı (eğer aktif ise)
                if not self.command_handler or self.command_handler.is_sending_enabled():
                    logger.info("📤 Sending fazı başlatılıyor...")
                    sending_stats = await self.run_auto_sending()

                    if self.status_reporter:
                        await self.status_reporter.send_sender_status(sending_stats)
                else:
                    logger.info("⏸️ Sending deaktif, atlanıyor...")

                # 3. Status raporu
                await self.send_periodic_status()

                # 4. Cycle tamamlandı, bekleme
                cycle_duration = (datetime.now() - cycle_start).seconds
                sleep_time = max(300, config.STATUS_INTERVAL - cycle_duration)  # Min 5 dk

                logger.info(f"⏳ Cycle tamamlandı, {sleep_time} saniye bekleniyor...")
                await asyncio.sleep(sleep_time)

        except Exception as e:
            logger.error(f"❌ Otomatik mod hatası: {str(e)}")
            if self.status_reporter:
                await self.status_reporter.send_error_status("Auto Mode Error", str(e))

    async def setup_auto_collector(self):
        """Otomatik collector kurulumu"""
        if not config.COLLECTOR_GROUPS:
            logger.error("❌ COLLECTOR_GROUPS boş!")
            return False

        # Collector client'ı account_manager'dan al (zaten başlatılmış)
        collector_session = config.COLLECTOR_SESSION
        collector_client = self.account_manager.get_active_client(collector_session)

        if not collector_client:
            logger.error(f"❌ Collector client bulunamadı: {collector_session}")
            return False

        # Collector'ın client'ını ata
        self.collector.client = collector_client

        # Grupları ekle ve entity cache'le
        for group in config.COLLECTOR_GROUPS:
            if group.strip():
                success = await self.collector.add_monitoring_group(group.strip())
                if success:
                    logger.info(f"✅ Grup eklendi: {group}")

                    # Entity caching yap (mesaj gönderimi için hazırlık)
                    try:
                        cached_count = await self.collector.cache_group_entities(group.strip(), limit=200)
                        logger.info(f"📦 {group} için {cached_count} entity cache'lendi")
                    except Exception as e:
                        logger.warning(f"⚠️ Entity caching hatası {group}: {str(e)}")
                else:
                    logger.warning(f"❌ Grup eklenemedi: {group}")

        return True

    async def run_auto_collection(self) -> dict:
        """Otomatik collection - SADECE CANLI DİNLEME"""
        stats = {'session_collected': 0, 'total_collected': 0}

        try:
            # ⚠️ GEÇMİŞ MESAJ TARAMA KAPALI
            logger.info("📡 Sadece canlı mesaj dinleme aktif (geçmiş tarama YOK)")

            # Canlı dinleme zaten kurulu, sadece istatistik güncellemesi yap
            # Yeni toplanan üye sayısını al (son 5 dakikadaki canlı mesajlar)
            db_stats = self.db.get_session_stats()

            # Bu session'da kaç kişi toplandığını hesapla
            current_active = db_stats['active_members']
            previous_active = getattr(self, '_previous_active_count', 0)
            session_collected = max(0, current_active - previous_active)

            stats['session_collected'] = session_collected
            stats.update(db_stats)

            # Sonraki karşılaştırma için kaydet
            self._previous_active_count = current_active

            if session_collected > 0:
                logger.info(f"📊 Canlı dinleme: {session_collected} yeni aktif üye")
            else:
                logger.info("📡 Canlı dinleme devam ediyor (yeni mesaj yok)")

        except Exception as e:
            logger.error(f"❌ Canlı dinleme kontrolü hatası: {str(e)}")
            if self.status_reporter:
                await self.status_reporter.send_error_status("Live Listening Error", str(e))

        return stats

    async def run_auto_sending(self) -> dict:
        """Otomatik mesaj gönderimi"""
        stats = {
            'session_sent': 0,
            'session_failed': 0,
            'success_rate': 0,
            'estimated_time': 'N/A'
        }

        try:
            # Hedefleri al (önce aktif üyeler)
            targets = self.db.get_uncontacted_members(
                limit=config.MESSAGES_PER_HOUR,
                source="active"
            )

            if not targets:
                # Aktif üye yoksa static'ten al
                targets = self.db.get_uncontacted_members(
                    limit=config.MESSAGES_PER_HOUR,
                    source="static"
                )

            if targets:
                logger.info(f"🎯 {len(targets)} hedef bulundu, mesaj gönderimi başlıyor...")

                # Mesaj gönder
                results = await self.sender.send_messages_batch(targets, config.BATCH_SIZE)

                stats['session_sent'] = results['sent']
                stats['session_failed'] = results['failed']

                # Başarı oranını hesapla
                total = results['sent'] + results['failed']
                if total > 0:
                    stats['success_rate'] = int((results['sent'] / total) * 100)

                # Session stats güncelle
                self.session_stats['sent_messages'] += results['sent']
                self.session_stats['failed_messages'] += results['failed']

                logger.info(f"📊 Gönderim tamamlandı: {results['sent']} başarılı, {results['failed']} başarısız")

                # Tahmini süre
                estimation = self.sender.estimate_completion_time()
                if estimation['remaining_messages'] > 0:
                    stats['estimated_time'] = utils.format_time_remaining(estimation['estimated_seconds'])
            else:
                logger.info("📭 Gönderilecek hedef bulunamadı")

        except Exception as e:
            logger.error(f"❌ Sending hatası: {str(e)}")
            if self.status_reporter:
                await self.status_reporter.send_error_status("Sending Error", str(e))

        return stats

    async def send_periodic_status(self):
        """Periyodik durum raporu gönder"""
        if self.status_reporter:
            try:
                db_stats = self.db.get_session_stats()

                status_message = f"""📊 **PERİYODİK RAPOR**

👥 **Kullanıcı Durumu:**
• Aktif üyeler: {db_stats['active_members']:,}
• Kalan hedef: {db_stats['remaining_members']:,}

📤 **Mesaj Durumu:**
• Toplam gönderilen: {db_stats['sent_messages']:,}
• Bugün gönderilen: {db_stats['messages_today']:,}

⏱️ **Çalışma Süresi:** {self.get_uptime()}
🔄 **Durum:** Sistem aktif çalışıyor"""

                await self.status_reporter.send_status(status_message)

            except Exception as e:
                logger.error(f"Status raporu hatası: {e}")

    def get_uptime(self) -> str:
        """Çalışma süresini formatla"""
        uptime = datetime.now() - self.start_time
        hours = uptime.seconds // 3600
        minutes = (uptime.seconds % 3600) // 60
        return f"{uptime.days} gün {hours} saat {minutes} dakika"

    async def cleanup(self):
        """Temizlik işlemleri"""
        try:
            self.running = False
            await self.account_manager.disconnect_all()
            await self.collector.stop_collecting()
            logger.info("🧹 Temizlik tamamlandı")
        except Exception as e:
            logger.error(f"Temizlik hatası: {str(e)}")

# Signal handler for graceful shutdown
def signal_handler(signum, frame):
    logger.info("👋 Program sonlandırılıyor...")
    sys.exit(0)

async def main():
    """Ana fonksiyon"""
    # Signal handler'ı kur
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Logging'i başlat
    utils.setup_logging()

    # Ana uygulama
    app = TelegramMassMessenger()

    try:
        # Sistemi başlat
        if not await app.initialize():
            logger.error("❌ Sistem başlatılamadı!")
            return

        # Otomatik mod (Heroku için optimize)
        logger.info("🤖 Otomatik mod başlatılıyor...")
        await app.run_auto_mode()

    except KeyboardInterrupt:
        logger.info("⏹️ Program kullanıcı tarafından durduruldu")
    except Exception as e:
        logger.error(f"❌ Ana program hatası: {str(e)}")
    finally:
        await app.cleanup()

if __name__ == "__main__":
    # Event loop'u çalıştır
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Güle güle!")
    except Exception as e:
        print(f"❌ Kritik hata: {str(e)}")
        sys.exit(1)
