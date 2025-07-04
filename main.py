"""
Telegram Mass Messenger - Ana Program - DÜZELTILMIŞ VERSİYON
Tamamen otomatik çalışan sistem (Heroku için optimize)
"""

import asyncio
import logging
import sys
import os
import signal
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, Union

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

        # Ana bileşenler
        self.db: Optional[DatabaseManager] = None
        self.account_manager: Optional[AccountManager] = None
        self.collector: Optional[MessageCollector] = None
        self.sender: Optional[MessageSender] = None
        self.scraper: Optional[GroupScraper] = None
        self.status_reporter: Optional[StatusReporter] = None
        self.command_handler: Optional[CommandHandler] = None

        # Sistem durumu
        self.running = False
        self.start_time = datetime.now()

        # Session istatistikleri
        self.session_stats = {
            'collected_users': 0,
            'sent_messages': 0,
            'failed_messages': 0,
            'errors': [],
            'cycles_completed': 0
        }

        # Önceki active count tracking
        self._previous_active_count = 0

    async def initialize(self) -> bool:
        """Sistemi başlat"""
        logger.info("🚀 Sistem başlatılıyor...")

        try:
            # 1. Database'i başlat
            if not await self._initialize_database():
                return False

            # 2. Account manager'ı başlat
            if not await self._initialize_account_manager():
                return False

            # 3. Diğer bileşenleri başlat
            if not await self._initialize_components():
                return False

            # 4. Status ve command handler'ları başlat
            if not await self._initialize_status_and_commands():
                return False

            # 5. Collector'ı kur
            if not await self._setup_collector():
                return False

            logger.info(f"✅ Sistem başarıyla başlatıldı - {len(self.account_manager.active_accounts)} hesap aktif")
            return True

        except Exception as e:
            logger.error(f"❌ Sistem başlatma hatası: {str(e)}")
            return False

    async def _initialize_database(self) -> bool:
        """Database'i başlat"""
        try:
            logger.info("🗄️ Database başlatılıyor...")
            self.db = DatabaseManager()

            # Veri sıfırlama kontrolü
            if config.RESET_DATA:
                logger.info("🗑️ Veri sıfırlama aktif - tüm veriler temizleniyor...")
                self.db.reset_all_data()

            return True
        except Exception as e:
            logger.error(f"❌ Database başlatma hatası: {str(e)}")
            return False

    async def _initialize_account_manager(self) -> bool:
        """Account manager'ı başlat"""
        try:
            logger.info("📱 Account manager başlatılıyor...")

            # Session dosyalarını kontrol et
            session_files = utils.check_session_files()
            if not session_files:
                logger.error("❌ Session dosyası bulunamadı!")
                return False

            logger.info(f"📁 {len(session_files)} session dosyası bulundu")

            # Account manager'ı başlat
            self.account_manager = AccountManager()
            success = await self.account_manager.initialize_clients()

            if not success:
                logger.error("❌ Hiç hesap başlatılamadı!")
                return False

            return True
        except Exception as e:
            logger.error(f"❌ Account manager başlatma hatası: {str(e)}")
            return False

    async def _initialize_components(self) -> bool:
        """Diğer bileşenleri başlat"""
        try:
            logger.info("🔧 Bileşenler başlatılıyor...")

            self.collector = MessageCollector(self.db)
            self.sender = MessageSender(self.db, self.account_manager)
            self.scraper = GroupScraper(self.db)

            return True
        except Exception as e:
            logger.error(f"❌ Bileşen başlatma hatası: {str(e)}")
            return False

    async def _initialize_status_and_commands(self) -> bool:
        """Status reporter ve command handler'ı başlat"""
        try:
            if not self.account_manager.active_accounts:
                logger.error("❌ Aktif hesap yok")
                return False

            # İlk hesabı status ve command için kullan
            first_account = self.account_manager.active_accounts[0]
            status_client = self.account_manager.get_active_client(first_account['session_name'])

            if not status_client:
                logger.error("❌ Status client alınamadı")
                return False

            # Status reporter'ı başlat
            logger.info("📊 Status reporter başlatılıyor...")
            self.status_reporter = StatusReporter(status_client)

            # Command handler'ı başlat
            logger.info("🎮 Command handler başlatılıyor...")
            self.command_handler = CommandHandler(self, self.status_reporter)

            command_setup_success = await self.command_handler.setup_command_listener(status_client)
            if not command_setup_success:
                logger.warning("⚠️ Command handler kurulamadı, devam ediliyor...")

            # Message sender'a command handler referansını ver
            self.sender.set_command_handler(self.command_handler)

            # Başlangıç status mesajı gönder
            try:
                await self.status_reporter.send_startup_status(
                    len(self.account_manager.active_accounts),
                    config.COLLECTOR_GROUPS
                )

                # Komut menüsünü gönder
                if self.command_handler:
                    help_text = self.command_handler.get_help_text()
                    await self.status_reporter.send_status(f"🎮 **KOMUTLAR HAZIR**\n\n{help_text}", force=True)

            except Exception as e:
                logger.warning(f"⚠️ Status mesajı gönderilemedi: {str(e)}")

            return True

        except Exception as e:
            logger.error(f"❌ Status/Command başlatma hatası: {str(e)}")
            return False

    async def _setup_collector(self) -> bool:
        """Collector'ı kur"""
        try:
            if not config.COLLECTOR_GROUPS:
                logger.error("❌ COLLECTOR_GROUPS boş!")
                return False

            # Collector client'ı account_manager'dan al
            collector_session = config.COLLECTOR_SESSION
            collector_client = self.account_manager.get_active_client(collector_session)

            if not collector_client:
                logger.error(f"❌ Collector client bulunamadı: {collector_session}")
                return False

            # Collector'ın client'ını ata
            self.collector.client = collector_client

            # Grupları ekle ve entity cache'le
            successful_groups = 0
            for group in config.COLLECTOR_GROUPS:
                if group and group.strip():
                    try:
                        success = await self.collector.add_monitoring_group(group.strip())
                        if success:
                            logger.info(f"✅ Grup eklendi: {group}")
                            successful_groups += 1

                            # Entity caching yap (mesaj gönderimi için hazırlık)
                            try:
                                cached_count = await self.collector.cache_group_entities(group.strip(), limit=200)
                                logger.info(f"📦 {group} için {cached_count} entity cache'lendi")
                            except Exception as e:
                                logger.warning(f"⚠️ Entity caching hatası {group}: {str(e)}")
                        else:
                            logger.warning(f"❌ Grup eklenemedi: {group}")
                    except Exception as e:
                        logger.error(f"❌ Grup ekleme hatası {group}: {str(e)}")

            if successful_groups == 0:
                logger.error("❌ Hiç grup eklenemedi!")
                return False

            logger.info(f"✅ {successful_groups}/{len(config.COLLECTOR_GROUPS)} grup başarıyla eklendi")
            return True

        except Exception as e:
            logger.error(f"❌ Collector setup hatası: {str(e)}")
            return False

    async def run_auto_mode(self):
        """Tamamen otomatik mod - Komutlarla kontrol edilebilir"""
        logger.info("🤖 Otomatik mod başlatılıyor...")

        try:
            self.running = True
            cycle_count = 0

            while self.running:
                cycle_count += 1
                cycle_start = datetime.now()

                logger.info(f"🔄 Cycle {cycle_count} başlatılıyor...")

                # Sistem durdurulmuşsa bekle
                if self.command_handler and not self.command_handler.is_system_running():
                    logger.info("⏸️ Sistem durduruldu, bekleniyor...")
                    await asyncio.sleep(30)
                    continue

                # 1. Collection fazı (eğer aktif ise)
                collection_stats = {}
                if not self.command_handler or self.command_handler.is_collecting_enabled():
                    logger.info("📡 Collection fazı başlatılıyor...")
                    collection_stats = await self.run_auto_collection()

                    if self.status_reporter and collection_stats:
                        try:
                            await self.status_reporter.send_collector_status(collection_stats)
                        except Exception as e:
                            logger.warning(f"⚠️ Collector status gönderilemedi: {str(e)}")
                else:
                    logger.info("⏸️ Collection deaktif, atlanıyor...")

                # 2. Sending fazı (eğer aktif ise)
                sending_stats = {}
                if not self.command_handler or self.command_handler.is_sending_enabled():
                    logger.info("📤 Sending fazı başlatılıyor...")
                    sending_stats = await self.run_auto_sending()

                    if self.status_reporter and sending_stats:
                        try:
                            await self.status_reporter.send_sender_status(sending_stats)
                        except Exception as e:
                            logger.warning(f"⚠️ Sender status gönderilemedi: {str(e)}")
                else:
                    logger.info("⏸️ Sending deaktif, atlanıyor...")

                # 3. Status raporu
                await self.send_periodic_status(cycle_count)

                # 4. Cycle tamamlandı
                self.session_stats['cycles_completed'] = cycle_count
                cycle_duration = (datetime.now() - cycle_start).seconds
                sleep_time = max(300, config.STATUS_INTERVAL - cycle_duration)  # Min 5 dk

                logger.info(f"✅ Cycle {cycle_count} tamamlandı ({cycle_duration}s), {sleep_time} saniye bekleniyor...")
                await asyncio.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("⏹️ Sistem kullanıcı tarafından durduruldu")
        except Exception as e:
            logger.error(f"❌ Otomatik mod hatası: {str(e)}")
            if self.status_reporter:
                try:
                    await self.status_reporter.send_error_status("Auto Mode Error", str(e))
                except:
                    pass
        finally:
            self.running = False

    async def run_auto_collection(self) -> Dict[str, Union[int, str]]:
        """Otomatik collection - SADECE CANLI DİNLEME"""
        stats = {'session_collected': 0, 'total_collected': 0, 'last_collection_time': 'N/A'}

        try:
            # ⚠️ GEÇMİŞ MESAJ TARAMA KAPALI
            logger.info("📡 Sadece canlı mesaj dinleme aktif (geçmiş tarama YOK)")

            # Canlı dinleme zaten kurulu, sadece istatistik güncellemesi yap
            db_stats = self.db.get_session_stats()

            # Bu session'da kaç kişi toplandığını hesapla
            current_active = db_stats.get('active_members', 0)
            session_collected = max(0, current_active - self._previous_active_count)

            stats.update({
                'session_collected': session_collected,
                'total_collected': current_active,
                'last_collection_time': datetime.now().strftime('%H:%M:%S'),
                **db_stats
            })

            # Sonraki karşılaştırma için kaydet
            self._previous_active_count = current_active

            # Session stats güncelle
            self.session_stats['collected_users'] += session_collected

            if session_collected > 0:
                logger.info(f"📊 Canlı dinleme: {session_collected} yeni aktif üye")
            else:
                logger.info("📡 Canlı dinleme devam ediyor (yeni mesaj yok)")

        except Exception as e:
            logger.error(f"❌ Canlı dinleme kontrolü hatası: {str(e)}")
            if self.status_reporter:
                try:
                    await self.status_reporter.send_error_status("Live Listening Error", str(e))
                except:
                    pass

        return stats

    async def run_auto_sending(self) -> Dict[str, Union[int, str]]:
        """Otomatik mesaj gönderimi"""
        stats = {
            'session_sent': 0,
            'session_failed': 0,
            'success_rate': 0,
            'estimated_time': 'N/A',
            'total_sent_db': 0,
            'remaining_targets': 0,
            'active_accounts': 0
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

                stats.update({
                    'session_sent': results.get('sent', 0),
                    'session_failed': results.get('failed', 0),
                    'total_targets': results.get('total_targets', 0)
                })

                # Başarı oranını hesapla
                total = stats['session_sent'] + stats['session_failed']
                if total > 0:
                    stats['success_rate'] = int((stats['session_sent'] / total) * 100)

                # Session stats güncelle
                self.session_stats['sent_messages'] += stats['session_sent']
                self.session_stats['failed_messages'] += stats['session_failed']

                logger.info(f"📊 Gönderim tamamlandı: {stats['session_sent']} başarılı, {stats['session_failed']} başarısız")

                # Tahmini süre
                try:
                    estimation = self.sender.estimate_completion_time()
                    if estimation.get('remaining_messages', 0) > 0:
                        stats['estimated_time'] = utils.format_time_remaining(estimation.get('estimated_seconds', 0))

                    # Ek istatistikler
                    sender_stats = self.sender.get_sender_stats()
                    stats.update({
                        'total_sent_db': sender_stats.get('total_sent_db', 0),
                        'remaining_targets': sender_stats.get('remaining_targets', 0),
                        'active_accounts': sender_stats.get('active_accounts', 0)
                    })

                except Exception as e:
                    logger.warning(f"⚠️ Tahmini süre hesaplanamadı: {str(e)}")
            else:
                logger.info("📭 Gönderilecek hedef bulunamadı")

                # Yine de istatistikleri al
                try:
                    sender_stats = self.sender.get_sender_stats()
                    stats.update({
                        'total_sent_db': sender_stats.get('total_sent_db', 0),
                        'remaining_targets': sender_stats.get('remaining_targets', 0),
                        'active_accounts': sender_stats.get('active_accounts', 0)
                    })
                except Exception as e:
                    logger.warning(f"⚠️ Sender stats alınamadı: {str(e)}")

        except Exception as e:
            logger.error(f"❌ Sending hatası: {str(e)}")
            if self.status_reporter:
                try:
                    await self.status_reporter.send_error_status("Sending Error", str(e))
                except:
                    pass

        return stats

    async def send_periodic_status(self, cycle_count: int):
        """Periyodik durum raporu gönder"""
        if not self.status_reporter:
            return

        try:
            # Her 5 cycle'da bir detaylı rapor gönder
            if cycle_count % 5 == 0:
                db_stats = self.db.get_session_stats()

                status_message = f"""📊 **PERİYODİK RAPOR** (Cycle {cycle_count})

👥 **Kullanıcı Durumu:**
• Aktif üyeler: {db_stats.get('active_members', 0):,}
• Kalan hedef: {db_stats.get('remaining_members', 0):,}

📤 **Mesaj Durumu:**
• Toplam gönderilen: {db_stats.get('sent_messages', 0):,}
• Bugün gönderilen: {db_stats.get('messages_today', 0):,}
• Bu oturumda: {self.session_stats['sent_messages']:,}

⏱️ **Sistem Bilgisi:**
• Çalışma süresi: {self.get_uptime()}
• Tamamlanan cycle: {cycle_count}
• Toplanan üye (session): {self.session_stats['collected_users']:,}

🔄 **Durum:** Sistem aktif çalışıyor"""

                await self.status_reporter.send_status(status_message)

        except Exception as e:
            logger.error(f"Status raporu hatası: {e}")

    def get_uptime(self) -> str:
        """Çalışma süresini formatla"""
        try:
            uptime = datetime.now() - self.start_time
            days = uptime.days
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60

            if days > 0:
                return f"{days} gün {hours} saat {minutes} dakika"
            elif hours > 0:
                return f"{hours} saat {minutes} dakika"
            else:
                return f"{minutes} dakika"
        except Exception:
            return "Hesaplanamadı"

    async def cleanup(self):
        """Temizlik işlemleri"""
        try:
            logger.info("🧹 Temizlik başlatılıyor...")

            self.running = False

            # Database connections'ı kapat
            if self.db:
                try:
                    self.db.close_connections()
                except Exception as e:
                    logger.error(f"Database kapatma hatası: {e}")

            # Account manager'ı temizle
            if self.account_manager:
                try:
                    await self.account_manager.disconnect_all()
                except Exception as e:
                    logger.error(f"Account disconnect hatası: {e}")

            # Collector'ı durdur
            if self.collector:
                try:
                    await self.collector.stop_collecting()
                except Exception as e:
                    logger.error(f"Collector durdurma hatası: {e}")

            logger.info("🧹 Temizlik tamamlandı")

        except Exception as e:
            logger.error(f"Temizlik hatası: {str(e)}")

    def get_system_status(self) -> Dict[str, Any]:
        """Sistem durumunu getir"""
        try:
            return {
                'running': self.running,
                'uptime': self.get_uptime(),
                'start_time': self.start_time,
                'session_stats': self.session_stats.copy(),
                'active_accounts': len(self.account_manager.active_accounts) if self.account_manager else 0,
                'monitoring_groups': len(self.collector.monitoring_groups) if self.collector else 0
            }
        except Exception as e:
            logger.error(f"System status hatası: {e}")
            return {}

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
        logger.info("🚀 Sistem başlatma denemesi...")
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
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        try:
            await app.cleanup()
        except Exception as e:
            logger.error(f"Cleanup hatası: {e}")

if __name__ == "__main__":
    # Event loop'u çalıştır
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Güle güle!")
    except Exception as e:
        print(f"❌ Kritik hata: {str(e)}")
        sys.exit(1)
