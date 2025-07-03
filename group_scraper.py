"""
Telegram Grup Scraper Modülü
Grup üyelerini static olarak toplar
"""

import logging
import asyncio
from typing import List, Dict, Optional
from telethon import TelegramClient
from telethon.tl.types import User, UserEmpty
from telethon.errors import FloodWaitError, ChannelPrivateError, ChatAdminRequiredError
import config
from database import DatabaseManager

logger = logging.getLogger(__name__)

class GroupScraper:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.client = None
        self.scraped_groups = []

    async def setup_scraper_client(self, client: TelegramClient):
        """Scraper client'ını kur"""
        self.client = client
        logger.info("🔍 Group scraper client kuruldu")

    async def scrape_group_members(self, group_identifier: str, limit: int = None) -> int:
        """Grup üyelerini static olarak scrape et"""
        if not self.client:
            logger.error("❌ Client bağlantısı yok!")
            return 0

        try:
            # Grup entity'sini al
            group_clean = group_identifier.strip().replace('@', '')
            entity = await self.client.get_entity(group_clean)

            group_info = {
                'id': entity.id,
                'title': getattr(entity, 'title', group_clean),
                'username': getattr(entity, 'username', None)
            }

            logger.info(f"🔍 {group_info['title']} üyeleri scrape ediliyor...")

            scraped_count = 0
            members_batch = []

            # Tüm üyeleri al
            async for participant in self.client.iter_participants(
                entity,
                limit=limit,
                aggressive=True
            ):
                if isinstance(participant, User) and not isinstance(participant, UserEmpty):
                    # Filtreleme
                    if self._should_exclude_user(participant):
                        continue

                    # Üye verisini hazırla
                    member_data = {
                        'user_id': participant.id,
                        'username': participant.username,
                        'first_name': participant.first_name,
                        'last_name': participant.last_name,
                        'phone': participant.phone,
                        'is_bot': participant.bot,
                        'is_admin': False,  # Bu ayrıca kontrol edilebilir
                        'group_id': group_info['id'],
                        'group_title': group_info['title']
                    }

                    members_batch.append(member_data)
                    scraped_count += 1

                    # Batch işleme
                    if len(members_batch) >= 100:
                        self.db.add_group_members(members_batch)
                        members_batch = []
                        logger.info(f"   📊 {scraped_count} üye işlendi...")

                    # Rate limiting
                    if scraped_count % 1000 == 0:
                        logger.info(f"   🔄 {scraped_count} üye tamamlandı, kısa mola...")
                        await asyncio.sleep(2)

            # Kalan batch'i işle
            if members_batch:
                self.db.add_group_members(members_batch)

            # Grup bilgisini kaydet
            self.scraped_groups.append({
                **group_info,
                'scraped_members': scraped_count,
                'scraped_at': asyncio.get_event_loop().time()
            })

            logger.info(f"✅ {group_info['title']}: {scraped_count} üye scrape edildi")
            return scraped_count

        except FloodWaitError as e:
            logger.warning(f"⏳ Flood wait {group_identifier}: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            return 0
        except (ChannelPrivateError, ChatAdminRequiredError):
            logger.error(f"❌ Grup erişimi yok: {group_identifier}")
            return 0
        except Exception as e:
            logger.error(f"❌ Scrape hatası {group_identifier}: {str(e)}")
            return 0

    async def scrape_multiple_groups(self, group_list: List[str], limit_per_group: int = None) -> Dict:
        """Birden fazla grubu scrape et"""
        results = {
            'total_scraped': 0,
            'successful_groups': 0,
            'failed_groups': 0,
            'group_results': []
        }

        logger.info(f"🎯 {len(group_list)} grup scrape edilecek...")

        for i, group in enumerate(group_list, 1):
            logger.info(f"📋 Grup {i}/{len(group_list)}: {group}")

            scraped = await self.scrape_group_members(group, limit_per_group)

            group_result = {
                'group': group,
                'scraped_count': scraped,
                'success': scraped > 0
            }

            results['group_results'].append(group_result)
            results['total_scraped'] += scraped

            if scraped > 0:
                results['successful_groups'] += 1
            else:
                results['failed_groups'] += 1

            # Gruplar arası bekleme
            if i < len(group_list):  # Son grup değilse
                await asyncio.sleep(5)

        logger.info(f"🎯 Scraping tamamlandı: {results['total_scraped']} toplam üye")
        return results

    async def update_group_members(self, group_identifier: str) -> int:
        """Mevcut grup üyelerini güncelle"""
        if not self.client:
            logger.error("❌ Client bağlantısı yok!")
            return 0

        try:
            # Önce eski verileri temizle
            group_clean = group_identifier.strip().replace('@', '')
            entity = await self.client.get_entity(group_clean)

            # Bu grubun eski kayıtlarını sil
            await self._delete_group_records(entity.id)

            # Yeniden scrape et
            return await self.scrape_group_members(group_identifier)

        except Exception as e:
            logger.error(f"❌ Grup güncelleme hatası {group_identifier}: {str(e)}")
            return 0

    async def _delete_group_records(self, group_id: int):
        """Belirli grubun kayıtlarını sil"""
        try:
            # Database'den bu grup üyelerini sil
            # PostgreSQL versiyonu
            import psycopg2

            with self.db.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('DELETE FROM group_members WHERE group_id = %s', (group_id,))
                    deleted_count = cursor.rowcount
                    conn.commit()

            logger.info(f"🗑️ {group_id} grubundan {deleted_count} eski kayıt silindi")

        except Exception as e:
            logger.error(f"❌ Grup kayıt silme hatası {group_id}: {str(e)}")

    def _should_exclude_user(self, user: User) -> bool:
        """Kullanıcının hariç tutulup tutulmayacağını kontrol et"""
        # Bot kontrolü
        if config.EXCLUDE_BOTS and user.bot:
            return True

        # Silinmiş hesap kontrolü
        if config.EXCLUDE_DELETED_ACCOUNTS and user.deleted:
            return True

        # Boş kullanıcı kontrolü
        if isinstance(user, UserEmpty):
            return True

        # ID kontrolü
        if not user.id or user.id <= 0:
            return True

        return False

    async def get_group_info(self, group_identifier: str) -> Optional[Dict]:
        """Grup bilgilerini al"""
        if not self.client:
            return None

        try:
            group_clean = group_identifier.strip().replace('@', '')
            entity = await self.client.get_entity(group_clean)

            return {
                'id': entity.id,
                'title': getattr(entity, 'title', 'Unknown'),
                'username': getattr(entity, 'username', None),
                'participants_count': getattr(entity, 'participants_count', 0),
                'is_channel': hasattr(entity, 'broadcast'),
                'is_group': not hasattr(entity, 'broadcast')
            }

        except Exception as e:
            logger.error(f"❌ Grup bilgisi alınamadı {group_identifier}: {str(e)}")
            return None

    async def check_group_accessibility(self, group_list: List[str]) -> Dict:
        """Grup erişilebilirliğini kontrol et"""
        results = {
            'accessible': [],
            'inaccessible': [],
            'total_checked': len(group_list)
        }

        for group in group_list:
            info = await self.get_group_info(group)

            if info:
                results['accessible'].append({
                    'identifier': group,
                    **info
                })
                logger.info(f"✅ {group}: {info['title']} ({info['participants_count']} üye)")
            else:
                results['inaccessible'].append(group)
                logger.warning(f"❌ {group}: Erişilemez")

        logger.info(f"📊 Erişim kontrolü: {len(results['accessible'])}/{len(group_list)} grup erişilebilir")
        return results

    def get_scraping_stats(self) -> Dict:
        """Scraping istatistiklerini getir"""
        total_scraped = sum(g['scraped_members'] for g in self.scraped_groups)

        return {
            'scraped_groups': len(self.scraped_groups),
            'total_members_scraped': total_scraped,
            'groups': self.scraped_groups
        }

    async def export_group_members(self, group_identifier: str, file_path: str) -> bool:
        """Grup üyelerini dosyaya export et"""
        try:
            group_clean = group_identifier.strip().replace('@', '')
            entity = await self.client.get_entity(group_clean)

            members = []
            async for participant in self.client.iter_participants(entity):
                if isinstance(participant, User) and not self._should_exclude_user(participant):
                    members.append({
                        'id': participant.id,
                        'username': participant.username or 'N/A',
                        'first_name': participant.first_name or 'N/A',
                        'last_name': participant.last_name or 'N/A',
                        'phone': participant.phone or 'N/A'
                    })

            # CSV olarak kaydet
            import csv
            with open(file_path, 'w', newline='', encoding='utf-8') as file:
                if members:
                    writer = csv.DictWriter(file, fieldnames=members[0].keys())
                    writer.writeheader()
                    writer.writerows(members)

            logger.info(f"📄 {len(members)} üye {file_path} dosyasına export edildi")
            return True

        except Exception as e:
            logger.error(f"❌ Export hatası {group_identifier}: {str(e)}")
            return False

    async def get_admins_and_moderators(self, group_identifier: str) -> List[Dict]:
        """Grup admin ve moderatörlerini al"""
        admins = []

        try:
            if not self.client:
                return admins

            group_clean = group_identifier.strip().replace('@', '')
            entity = await self.client.get_entity(group_clean)

            # Admin/moderator katılımcıları al
            async for participant in self.client.iter_participants(
                entity,
                filter='admin'
            ):
                if isinstance(participant, User):
                    admins.append({
                        'user_id': participant.id,
                        'username': participant.username,
                        'first_name': participant.first_name,
                        'last_name': participant.last_name,
                        'is_bot': participant.bot
                    })

            logger.info(f"👑 {group_identifier}: {len(admins)} admin/moderator bulundu")

        except Exception as e:
            logger.error(f"❌ Admin listesi alınamadı {group_identifier}: {str(e)}")

        return admins

    def clear_scraped_data(self):
        """Scrape edilen veri istatistiklerini temizle"""
        self.scraped_groups.clear()
        logger.info("🗑️ Scrape istatistikleri temizlendi")
