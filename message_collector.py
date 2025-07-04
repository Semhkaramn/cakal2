"""
Telegram Mesaj Toplayıcı Modülü - DÜZELTILMIŞ VERSİYON
Gruplardaki SADECE ANLIK mesaj atan kullanıcıları toplar
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union, Any
from telethon import TelegramClient, events
from telethon.tl.types import User, Channel, Chat, UserEmpty
from telethon.errors import (
    FloodWaitError, ChannelPrivateError, ChatAdminRequiredError,
    UserNotParticipantError, RPCError
)
import config
from database import DatabaseManager

logger = logging.getLogger(__name__)

class MessageCollector:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.client: Optional[TelegramClient] = None
        self.monitoring_groups: List[Dict[str, Any]] = []
        self.is_collecting = False
        self.collected_users = 0
        self.collection_count = 0
        self.last_collection_time: Optional[datetime] = None

    async def setup_collector_client(self, session_name: str) -> bool:
        """Collector client'ını kur"""
        try:
            if not session_name:
                logger.error("❌ Session name sağlanmadı")
                return False

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

            if not group_identifier or not group_identifier.strip():
                logger.error("❌ Geçersiz grup identifier")
                return False

            # @ işaretini temizle
            group_clean = group_identifier.strip().replace('@', '')

            # Grubu bul
            try:
                entity = await self.client.get_entity(group_clean)

                if not entity:
                    logger.error(f"❌ Grup bulunamadı: {group_identifier}")
                    return False

                group_info = {
                    'id': entity.id,
                    'title': getattr(entity, 'title', group_clean),
                    'username': getattr(entity, 'username', None),
                    'identifier': group_identifier,
                    'entity_type': type(entity).__name__,
                    'is_active': True
                }

                # Grup zaten izleniyor mu kontrol et
                if any(g['id'] == group_info['id'] for g in self.monitoring_groups):
                    logger.warning(f"⚠️ Grup zaten izleniyor: {group_info['title']}")
                    return True

                self.monitoring_groups.append(group_info)

                # ANLIK mesaj dinlemesini başlat
                await self.setup_live_message_listener(entity, group_info)

                logger.info(f"✅ Grup eklendi: {group_info['title']} ({group_info['id']})")
                return True

            except (ChannelPrivateError, ChatAdminRequiredError) as e:
                logger.error(f"❌ Gruba erişim yok: {group_identifier} - {type(e).__name__}")
                return False
            except UserNotParticipantError:
                logger.error(f"❌ Gruba üye değilsiniz: {group_identifier}")
                return False
            except Exception as e:
                logger.error(f"❌ Grup bulunamadı {group_identifier}: {str(e)}")
                return False

        except Exception as e:
            logger.error(f"❌ Grup ekleme hatası: {str(e)}")
            return False

    async def setup_live_message_listener(self, entity, group_info: Dict[str, Any]):
        """Grup için canlı mesaj dinleyicisi kur"""
        try:
            if not self.client:
                logger.error("❌ Client bağlantısı yok")
                return

            @self.client.on(events.NewMessage(chats=entity))
            async def live_message_handler(event):
                try:
                    await self._handle_new_message(event, group_info)
                except Exception as e:
                    logger.error(f"❌ Live message handler hatası: {str(e)}")

            logger.info(f"📡 {group_info['title']} için CANLI mesaj dinleme başlatıldı")

        except Exception as e:
            logger.error(f"❌ {group_info['title']} canlı dinleme hatası: {str(e)}")

    async def collect_recent_messages(self, hours_back: int = 24, limit_per_group: int = 1000) -> int:
        """ARTIK KULLANILMIYOR - Sadece canlı mesajları dinliyoruz"""
        logger.info("📅 Geçmiş mesaj tarama devre dışı - Sadece canlı mesajlar toplanıyor")

        # Monitoring grupları sayısını logla
        if self.monitoring_groups:
            logger.info(f"🎯 Canlı dinleme aktif: {len(self.monitoring_groups)} grup")
            for group in self.monitoring_groups:
                if group.get('is_active'):
                    logger.info(f"   📡 Dinleniyor: {group['title']}")
        else:
            logger.warning("⚠️ Hiç monitoring grubu yok!")

        return 0

    async def start_collecting(self):
        """Canlı mesaj toplama başlat"""
        if not self.client:
            logger.error("❌ Client bağlantısı yok!")
            return

        if not self.monitoring_groups:
            logger.warning("⚠️ İzlenecek grup yok!")
            return

        self.is_collecting = True
        logger.info("🎯 SADECE CANLI mesaj dinleme aktif...")

        try:
            # Ana döngüde client çalışıyor, burada sadece aktif dinleme var
            logger.info("📡 Canlı mesaj dinleme devam ediyor...")

            # Monitoring gruplarının durumunu kontrol et
            await self._check_monitoring_groups_health()

        except KeyboardInterrupt:
            logger.info("⏹️ Canlı toplama durduruldu")
        except Exception as e:
            logger.error(f"❌ Canlı toplama hatası: {str(e)}")
        finally:
            self.is_collecting = False

    async def _check_monitoring_groups_health(self):
        """Monitoring gruplarının sağlığını kontrol et"""
        try:
            healthy_groups = 0
            for group in self.monitoring_groups:
                if group.get('is_active'):
                    # Grup erişilebilirliğini test et
                    if await self._test_group_access(group['id']):
                        healthy_groups += 1
                    else:
                        group['is_active'] = False
                        logger.warning(f"⚠️ Grup erişilemez durumda: {group['title']}")

            logger.info(f"💊 Grup sağlık durumu: {healthy_groups}/{len(self.monitoring_groups)} aktif")

        except Exception as e:
            logger.error(f"❌ Grup sağlık kontrolü hatası: {str(e)}")

    async def _test_group_access(self, group_id: int) -> bool:
        """Gruba erişim testi"""
        try:
            if not self.client:
                return False

            entity = await self.client.get_entity(group_id)
            return entity is not None

        except Exception:
            return False

    async def _handle_new_message(self, event, group_info: Dict[str, Any]):
        """Yeni (CANLI) mesaj işle"""
        try:
            sender = event.sender

            if not sender or not isinstance(sender, User):
                return

            # Kullanıcı filtrelerini uygula
            if self._should_exclude_user(sender):
                return

            # Boş kullanıcı kontrolü
            if isinstance(sender, UserEmpty):
                logger.debug("Boş kullanıcı atlandı")
                return

            # ID doğrulaması
            if not self._is_valid_user_id(sender.id):
                logger.debug(f"Geçersiz user ID: {sender.id}")
                return

            # Aktif üye olarak HEMEN ekle
            member_data = {
                'user_id': sender.id,
                'username': getattr(sender, 'username', None),
                'first_name': getattr(sender, 'first_name', None),
                'last_name': getattr(sender, 'last_name', None),
                'phone': getattr(sender, 'phone', None),
                'is_bot': getattr(sender, 'bot', False),
                'is_admin': False,  # Bu grup context'inde kontrol edilebilir
                'group_id': group_info['id'],
                'group_title': group_info['title'],
                'message_date': event.date,
                'is_active': True
            }

            # Database'e ekle
            self.db.add_active_member(member_data)
            self.collected_users += 1
            self.last_collection_time = datetime.now()

            # Log mesajı
            display_name = (member_data['first_name'] or
                          member_data['username'] or
                          f"ID:{member_data['user_id']}")

            logger.info(f"📥 YENİ ANLIK ÜYE: {display_name} - {group_info['title']}")

            # Entity validation için test (opsiyonel)
            if config.VALIDATE_ENTITIES:
                try:
                    await self.client.get_entity(sender.id)
                    logger.debug(f"✅ Entity cached: {sender.id}")
                except Exception as e:
                    logger.debug(f"⚠️ Entity cache issue: {sender.id} - {str(e)}")

        except Exception as e:
            logger.error(f"❌ Canlı mesaj işleme hatası: {str(e)}")

    def _should_exclude_user(self, user: User) -> bool:
        """Kullanıcının hariç tutulup tutulmayacağını kontrol et"""
        try:
            # Bot kontrolü
            if config.EXCLUDE_BOTS and getattr(user, 'bot', False):
                return True

            # Silinmiş hesap kontrolü
            if config.EXCLUDE_DELETED_ACCOUNTS and getattr(user, 'deleted', False):
                return True

            # Kullanıcı adı ve isim kontrolü (spam hesap tespiti)
            username = getattr(user, 'username', None)
            first_name = getattr(user, 'first_name', None)

            # Tamamen boş profil
            if not username and not first_name:
                return True

            # Şüpheli username pattern'leri (opsiyonel)
            if username and len(username) > 50:  # Çok uzun username
                return True

            return False

        except Exception as e:
            logger.debug(f"User exclude check hatası: {e}")
            return True  # Hata durumunda exclude et

    def _is_valid_user_id(self, user_id: Union[int, str, None]) -> bool:
        """User ID doğrulaması"""
        try:
            if user_id is None:
                return False

            user_id = int(user_id)
            return config.MIN_USER_ID <= user_id <= config.MAX_USER_ID

        except (ValueError, TypeError):
            return False

    async def stop_collecting(self):
        """Mesaj toplamayı durdur"""
        self.is_collecting = False

        # Monitoring gruplarını deaktif et
        for group in self.monitoring_groups:
            group['is_active'] = False

        logger.info("⏹️ Canlı mesaj toplama durduruldu")

    def get_monitoring_stats(self) -> Dict[str, Union[int, List[str], bool, Optional[datetime]]]:
        """İzleme istatistiklerini getir"""
        try:
            active_groups = [g for g in self.monitoring_groups if g.get('is_active')]
            group_titles = [g['title'] for g in active_groups]

            return {
                'monitoring_groups': len(self.monitoring_groups),
                'active_groups': len(active_groups),
                'groups': group_titles,
                'is_collecting': self.is_collecting,
                'collected_users': self.collected_users,
                'collection_count': self.collection_count,
                'last_collection_time': self.last_collection_time
            }
        except Exception as e:
            logger.error(f"❌ Monitoring stats hatası: {e}")
            return {
                'monitoring_groups': 0,
                'active_groups': 0,
                'groups': [],
                'is_collecting': False,
                'collected_users': 0,
                'collection_count': 0,
                'last_collection_time': None
            }

    async def test_group_access(self, group_identifier: str) -> bool:
        """Grup erişimini test et"""
        try:
            if not self.client:
                logger.error("❌ Client bağlantısı yok")
                return False

            group_clean = group_identifier.strip().replace('@', '')
            entity = await self.client.get_entity(group_clean)

            if not entity:
                return False

            # 1 mesaj almayı dene
            try:
                async for message in self.client.iter_messages(entity, limit=1):
                    logger.info(f"✅ Grup erişimi OK: {getattr(entity, 'title', 'Unknown')}")
                    return True
            except Exception:
                pass

            return True

        except (ChannelPrivateError, ChatAdminRequiredError):
            logger.error(f"❌ Grup erişimi başarısız: {group_identifier} - Yetki sorunu")
            return False
        except UserNotParticipantError:
            logger.error(f"❌ Grup erişimi başarısız: {group_identifier} - Üye değilsiniz")
            return False
        except Exception as e:
            logger.error(f"❌ Grup erişimi başarısız {group_identifier}: {str(e)}")
            return False

    def clear_monitoring_groups(self):
        """İzleme gruplarını temizle"""
        self.monitoring_groups.clear()
        self.collected_users = 0
        self.collection_count = 0
        self.last_collection_time = None
        logger.info("🗑️ İzleme grupları temizlendi")

    async def collect_group_admins(self, group_id: int) -> List[int]:
        """Grup adminlerini topla"""
        admin_ids = []

        try:
            if not self.client:
                logger.error("❌ Client bağlantısı yok")
                return admin_ids

            entity = await self.client.get_entity(group_id)
            if not entity:
                return admin_ids

            # Admin listesini al
            async for participant in self.client.iter_participants(
                entity,
                filter='admin'
            ):
                if isinstance(participant, User) and not isinstance(participant, UserEmpty):
                    if self._is_valid_user_id(participant.id):
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

            if not entity:
                logger.error(f"❌ Grup bulunamadı: {group_identifier}")
                return 0

            logger.info(f"🔄 {getattr(entity, 'title', 'Unknown')} grubu entity cache'leniyor...")

            # Grup üyelerini al ve cache'le
            async for participant in self.client.iter_participants(
                entity,
                limit=limit
            ):
                if isinstance(participant, User) and not isinstance(participant, UserEmpty):
                    if not self._should_exclude_user(participant) and self._is_valid_user_id(participant.id):
                        try:
                            # Participant'ı alırken otomatik cache'lenir
                            cached_count += 1

                            if cached_count % 10 == 0:
                                logger.info(f"   📊 {cached_count} entity cache'lendi...")

                        except Exception as e:
                            logger.debug(f"Entity cache hatası {participant.id}: {e}")

            logger.info(f"✅ {cached_count} entity cache'lendi: {getattr(entity, 'title', 'Unknown')}")
            return cached_count

        except Exception as e:
            logger.error(f"❌ Entity cache hatası {group_identifier}: {str(e)}")
            return 0

    async def get_group_member_count(self, group_identifier: str) -> int:
        """Grup üye sayısını al"""
        try:
            if not self.client:
                return 0

            group_clean = group_identifier.strip().replace('@', '')
            entity = await self.client.get_entity(group_clean)

            if hasattr(entity, 'participants_count'):
                return entity.participants_count
            else:
                # Manuel sayma (yavaş)
                count = 0
                async for _ in self.client.iter_participants(entity):
                    count += 1
                return count

        except Exception as e:
            logger.error(f"❌ Grup üye sayısı alınamadı {group_identifier}: {str(e)}")
            return 0

    def get_collection_summary(self) -> Dict[str, Union[int, float, str]]:
        """Toplama özeti"""
        try:
            runtime_hours = 0
            if self.last_collection_time:
                runtime = datetime.now() - self.last_collection_time
                runtime_hours = runtime.total_seconds() / 3600

            collection_rate = self.collected_users / runtime_hours if runtime_hours > 0 else 0

            return {
                'total_collected': self.collected_users,
                'runtime_hours': round(runtime_hours, 2),
                'collection_rate_per_hour': round(collection_rate, 2),
                'active_groups': len([g for g in self.monitoring_groups if g.get('is_active')]),
                'last_collection': self.last_collection_time.strftime('%H:%M:%S') if self.last_collection_time else 'Henüz yok'
            }
        except Exception as e:
            logger.error(f"❌ Collection summary hatası: {e}")
            return {
                'total_collected': 0,
                'runtime_hours': 0,
                'collection_rate_per_hour': 0,
                'active_groups': 0,
                'last_collection': 'Hata'
            }

    async def validate_monitoring_groups(self) -> Dict[str, bool]:
        """Tüm monitoring gruplarını doğrula"""
        validation_results = {}

        for group in self.monitoring_groups:
            try:
                group_id = group['id']
                is_valid = await self._test_group_access(group_id)
                validation_results[group['title']] = is_valid

                if not is_valid:
                    group['is_active'] = False

            except Exception as e:
                logger.error(f"❌ Grup validasyon hatası {group.get('title', 'Unknown')}: {e}")
                validation_results[group.get('title', 'Unknown')] = False

        return validation_results

    def reset_stats(self):
        """İstatistikleri sıfırla"""
        self.collected_users = 0
        self.collection_count = 0
        self.last_collection_time = None
        logger.info("📊 Collector istatistikleri sıfırlandı")
