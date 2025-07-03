"""
Telegram Mesaj Toplayıcı Modülü
Gruplardaki SADECE ANLIK mesaj atan kullanıcıları toplar
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from telethon import TelegramClient, events
from telethon.tl.types import User, Channel, Chat
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatAdminRequiredError
import config
from database import DatabaseManager

logger = logging.getLogger(__name__)

class MessageCollector:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.client = None
        self.monitoring_groups = []
        self.is_collecting = False
        self.collected_users = 0
        self.collection_count = 0

    async def setup_collector_client(self, session_name: str) -> bool:
        """Collector client'ını kur"""
        try:
            # Client zaten account_manager'dan gelecek
            logger.info(f"📡 Collector client kuruldu: {session_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Collector client kurulamadı: {str(e)}")
            return False

    async def add_monitoring_group(self, group_identifier: str) -> bool:
        """İzlenecek grup ekle"""
        try:
            if not self.client:
                logger.error("❌ Client bağlantısı yok!")
                return False

            # @ işaretini temizle
            group_clean = group_identifier.strip().replace('@', '')

            # Grubu bul
            try:
                entity = await self.client.get_entity(group_clean)

                group_info = {
                    'id': entity.id,
                    'title': getattr(entity, 'title', group_clean),
                    'username': getattr(entity, 'username', None),
                    'identifier': group_identifier
                }

                self.monitoring_groups.append(group_info)

                # ANLIK mesaj dinlemesini başlat
                await self.setup_live_message_listener(entity, group_info)

                logger.info(f"✅ Grup eklendi: {group_info['title']} ({group_info['id']})")
                return True

            except (ChannelPrivateError, ChatAdminRequiredError):
                logger.error(f"❌ Gruba erişim yok: {group_identifier}")
                return False
            except Exception as e:
                logger.error(f"❌ Grup bulunamadı {group_identifier}: {str(e)}")
                return False

        except Exception as e:
            logger.error(f"❌ Grup ekleme hatası: {str(e)}")
            return False

    async def setup_live_message_listener(self, entity, group_info: Dict):
        """Grup için canlı mesaj dinleyicisi kur"""
        try:
            @self.client.on(events.NewMessage(chats=entity))
            async def live_message_handler(event):
                await self._handle_new_message(event, group_info)

            logger.info(f"📡 {group_info['title']} için CANLI mesaj dinleme başlatıldı")

        except Exception as e:
            logger.error(f"❌ {group_info['title']} canlı dinleme hatası: {str(e)}")

    async def collect_recent_messages(self, hours_back: int = 24, limit_per_group: int = 1000) -> int:
        """ARTIK KULLANILMIYOR - Sadece canlı mesajları dinliyoruz"""
        logger.info("📅 Geçmiş mesaj tarama devre dışı - Sadece canlı mesajlar toplanıyor")

        # Hemen 0 döndür, hiç geçmiş mesaj tarama
        total_collected = 0

        logger.info(f"🎯 Canlı dinleme aktif: {len(self.monitoring_groups)} grup")
        return total_collected

    async def start_collecting(self):
        """Canlı mesaj toplama başlat"""
        if not self.client:
            logger.error("❌ Client bağlantısı yok!")
            return

        self.is_collecting = True
        logger.info("🎯 SADECE CANLI mesaj dinleme aktif...")

        # Client çalışmaya devam etsin - zaten event listener'lar kurulu
        try:
            # Ana döngüde client çalışıyor olacak, burada sadece aktif dinleme var
            logger.info("📡 Canlı mesaj dinleme devam ediyor...")

        except KeyboardInterrupt:
            logger.info("⏹️ Canlı toplama durduruldu")
        finally:
            self.is_collecting = False

    async def _handle_new_message(self, event, group_info: Dict):
        """Yeni (CANLI) mesaj işle"""
        try:
            if event.sender and isinstance(event.sender, User):
                # Filtreleme
                if self._should_exclude_user(event.sender):
                    return
                # Entity'yi cache'e ekle (Telethon otomatik yapar)
                user = event.sender

                # Aktif üye olarak HEMEN ekle
                member_data = {
                    'user_id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'phone': user.phone,
                    'is_bot': user.bot,
                    'is_admin': False,
                    'group_id': group_info['id'],
                    'group_title': group_info['title'],
                    'message_date': event.date,
                    'is_active': True
                }

                self.db.add_active_member(member_data)
                self.collected_users += 1

                logger.info(f"📥 YENİ ANLIK ÜYE: {user.first_name or 'N/A'} (@{user.username or 'N/A'}) - {group_info['title']}")

                # Entity validation için test
                try:
                    # Entity'nin erişilebilir olduğunu doğrula
                    await self.client.get_entity(user.id)
                    logger.debug(f"✅ Entity cached: {user.id}")
                except Exception:
                    logger.debug(f"⚠️ Entity cache issue: {user.id}")

        except Exception as e:
            logger.error(f"❌ Canlı mesaj işleme hatası: {str(e)}")

    def _should_exclude_user(self, user: User) -> bool:
        """Kullanıcının hariç tutulup tutulmayacağını kontrol et"""
        # Bot kontrolü
        if config.EXCLUDE_BOTS and user.bot:
            return True

        # Silinmiş hesap kontrolü
        if config.EXCLUDE_DELETED_ACCOUNTS and user.deleted:
            return True

        # Admin kontrolü (bu grup context'inde yapılabilir)
        # Şimdilik skip

        return False

    async def stop_collecting(self):
        """Mesaj toplamayı durdur"""
        self.is_collecting = False
        logger.info("⏹️ Canlı mesaj toplama durduruldu")

    def get_monitoring_stats(self) -> Dict:
        """İzleme istatistiklerini getir"""
        return {
            'monitoring_groups': len(self.monitoring_groups),
            'groups': [g['title'] for g in self.monitoring_groups],
            'is_collecting': self.is_collecting,
            'collected_users': self.collected_users,
            'collection_count': self.collection_count
        }

    async def test_group_access(self, group_identifier: str) -> bool:
        """Grup erişimini test et"""
        try:
            if not self.client:
                return False

            group_clean = group_identifier.strip().replace('@', '')
            entity = await self.client.get_entity(group_clean)

            # 1 mesaj almayı dene
            async for message in self.client.iter_messages(entity, limit=1):
                logger.info(f"✅ Grup erişimi OK: {entity.title}")
                return True

            return True

        except Exception as e:
            logger.error(f"❌ Grup erişimi başarısız {group_identifier}: {str(e)}")
            return False

    def clear_monitoring_groups(self):
        """İzleme gruplarını temizle"""
        self.monitoring_groups.clear()
        logger.info("🗑️ İzleme grupları temizlendi")

    async def collect_group_admins(self, group_id: int) -> List[int]:
        """Grup adminlerini topla"""
        admin_ids = []

        try:
            if not self.client:
                return admin_ids

            # Admin listesini al
            async for participant in self.client.iter_participants(
                group_id,
                filter='admin'
            ):
                if isinstance(participant, User):
                    admin_ids.append(participant.id)

            logger.info(f"📋 {len(admin_ids)} admin bulundu: {group_id}")

        except Exception as e:
            logger.error(f"❌ Admin listesi alınamadı {group_id}: {str(e)}")

        return admin_ids

    async def cache_group_entities(self, group_identifier: str, limit: int = 100) -> int:
        """Grup üyelerini entity cache'ine ekle (mesaj gönderimi için hazırlık)"""
        cached_count = 0

        try:
            if not self.client:
                logger.error("❌ Client bağlantısı yok!")
                return 0

            group_clean = group_identifier.strip().replace('@', '')
            entity = await self.client.get_entity(group_clean)

            logger.info(f"🔄 {entity.title} grubu entity cache'leniyor...")

            # Grup üyelerini al ve cache'le
            async for participant in self.client.iter_participants(
                entity,
                limit=limit
            ):
                if isinstance(participant, User) and not self._should_exclude_user(participant):
                    try:
                        # Participant'ı alırken otomatik cache'lenir
                        cached_count += 1

                        if cached_count % 10 == 0:
                            logger.info(f"   📊 {cached_count} entity cache'lendi...")

                    except Exception as e:
                        logger.debug(f"Entity cache hatası {participant.id}: {e}")

            logger.info(f"✅ {cached_count} entity cache'lendi: {entity.title}")
            return cached_count

        except Exception as e:
            logger.error(f"❌ Entity cache hatası {group_identifier}: {str(e)}")
            return 0

