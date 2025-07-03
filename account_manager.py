"""
Telegram Hesap Yönetimi
Session dosyalarını otomatik algılar ve yönetir
"""

import os
import glob
import logging
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PeerFloodError
from typing import List, Dict, Optional
import config

logger = logging.getLogger(__name__)

class AccountManager:
    def __init__(self):
        self.clients: Dict[str, TelegramClient] = {}
        self.session_files = []
        self.active_accounts = []
        self.current_account_index = 0

    def discover_session_files(self) -> List[str]:
        """Session dosyalarını otomatik olarak bul"""
        session_patterns = [
            "*.session",
            "hesap*.session",
            "account*.session"
        ]

        session_files = []
        for pattern in session_patterns:
            session_files.extend(glob.glob(pattern))

        # Benzersiz dosyaları al ve sırala
        session_files = sorted(list(set(session_files)))
        logger.info(f"Bulunan session dosyaları: {session_files}")
        return session_files

    async def initialize_clients(self) -> bool:
        """Her hesap için ayrı API bilgileriyle client'ları başlat"""
        logger.info("🔄 Hesaplar başlatılıyor...")

        # 1. Collector hesabını başlat
        collector_success = await self.initialize_collector()

        # 2. Sender hesaplarını başlat
        sender_success = await self.initialize_senders()

        if not collector_success and not sender_success:
            logger.error("❌ Hiçbir hesap başlatılamadı!")
            return False

        logger.info(f"✅ Toplam {len(self.active_accounts)} hesap başlatıldı")
        return True

    async def initialize_collector(self) -> bool:
        """Collector hesabını başlat"""
        try:
            session_name = config.COLLECTOR_SESSION
            api_id = config.COLLECTOR_API_ID
            api_hash = config.COLLECTOR_API_HASH

            logger.info(f"📡 Collector başlatılıyor: {session_name}")

            client = TelegramClient(session_name, api_id, api_hash)
            await client.connect()

            if await client.is_user_authorized():
                me = await client.get_me()
                self.clients[session_name] = client
                self.active_accounts.append({
                    'session_name': session_name,
                    'phone': me.phone,
                    'name': f"{me.first_name or ''} {me.last_name or ''}".strip(),
                    'username': me.username,
                    'client': client,
                    'message_count': 0,
                    'is_active': True,
                    'role': 'collector',
                    'api_id': api_id,
                    'api_hash': api_hash
                })
                logger.info(f"✅ Collector başarılı: {me.phone} - {me.first_name}")
                return True
            else:
                logger.error(f"❌ Collector yetkilendirilmemiş: {session_name}")
                await client.disconnect()
                return False

        except Exception as e:
            logger.error(f"❌ Collector başlatılamadı: {str(e)}")
            return False

    async def initialize_senders(self) -> bool:
        """Sender hesaplarını başlat"""
        sender_success_count = 0

        for sender_config in config.SENDER_ACCOUNTS:
            try:
                session_name = sender_config['session_name']
                api_id = sender_config['api_id']
                api_hash = sender_config['api_hash']
                sender_num = sender_config['number']

                logger.info(f"📤 Sender{sender_num} başlatılıyor: {session_name}")

                client = TelegramClient(session_name, api_id, api_hash)
                await client.connect()

                if await client.is_user_authorized():
                    me = await client.get_me()
                    self.clients[session_name] = client
                    self.active_accounts.append({
                        'session_name': session_name,
                        'phone': me.phone,
                        'name': f"{me.first_name or ''} {me.last_name or ''}".strip(),
                        'username': me.username,
                        'client': client,
                        'message_count': 0,
                        'is_active': True,
                        'role': 'sender',
                        'sender_number': sender_num,
                        'api_id': api_id,
                        'api_hash': api_hash
                    })
                    logger.info(f"✅ Sender{sender_num} başarılı: {me.phone} - {me.first_name}")
                    sender_success_count += 1
                else:
                    logger.warning(f"❌ Sender{sender_num} yetkilendirilmemiş: {session_name}")
                    await client.disconnect()

            except Exception as e:
                logger.error(f"❌ Sender{sender_config['number']} başlatılamadı: {str(e)}")
                continue

        logger.info(f"📊 {sender_success_count}/{len(config.SENDER_ACCOUNTS)} sender hesabı başarılı")
        return sender_success_count > 0

    def get_next_account(self) -> Optional[Dict]:
        """Sıradaki SENDER hesabını al (collector hariç)"""
        if not self.active_accounts:
            return None

        # Sadece sender hesaplarını filtrele
        sender_accounts = [acc for acc in self.active_accounts if acc.get('role') == 'sender' and acc['is_active']]

        if not sender_accounts:
            logger.warning("❌ Aktif sender hesabı bulunamadı!")
            return None

        # En az mesaj gönderen sender hesabını bul
        account = min(sender_accounts, key=lambda x: x['message_count'])

        return account

    def deactivate_account(self, session_name: str, reason: str = ""):
        """Hesabı deaktif et"""
        for account in self.active_accounts:
            if account['session_name'] == session_name:
                account['is_active'] = False
                logger.warning(f"🔒 {session_name} deaktif edildi: {reason}")
                break

    def increment_message_count(self, session_name: str):
        """Hesabın mesaj sayısını artır"""
        for account in self.active_accounts:
            if account['session_name'] == session_name:
                account['message_count'] += 1
                break

    async def test_account(self, session_name: str) -> bool:
        """Hesabın çalışır durumda olup olmadığını test et"""
        try:
            if session_name in self.clients:
                client = self.clients[session_name]
                me = await client.get_me()
                return True
        except Exception as e:
            logger.error(f"❌ {session_name} test başarısız: {str(e)}")
            self.deactivate_account(session_name, f"Test başarısız: {str(e)}")
            return False
        return False

    def get_account_stats(self) -> Dict:
        """Hesap istatistiklerini getir"""
        total_accounts = len(self.active_accounts)
        active_count = sum(1 for acc in self.active_accounts if acc['is_active'])
        total_messages = sum(acc['message_count'] for acc in self.active_accounts)

        return {
            'total_accounts': total_accounts,
            'active_accounts': active_count,
            'inactive_accounts': total_accounts - active_count,
            'total_messages_sent': total_messages,
            'accounts': self.active_accounts
        }

    async def disconnect_all(self):
        """Tüm client'ları disconnect et"""
        for client in self.clients.values():
            try:
                await client.disconnect()
            except:
                pass
        logger.info("Tüm hesaplar disconnect edildi")

    def get_active_client(self, session_name: str) -> Optional[TelegramClient]:
        """Aktif client'ı getir"""
        return self.clients.get(session_name)

    async def handle_flood_wait(self, session_name: str, seconds: int):
        """Flood wait hatası yönetimi"""
        logger.warning(f"⏳ {session_name} için {seconds} saniye flood wait")

        # Eğer çok uzun süreli ise hesabı geçici olarak deaktif et
        if seconds > 300:  # 5 dakikadan fazla
            self.deactivate_account(session_name, f"Uzun flood wait: {seconds}s")
        else:
            # Kısa süreli ise bekle
            await asyncio.sleep(seconds)

    async def handle_peer_flood(self, session_name: str):
        """Peer flood hatası yönetimi"""
        logger.error(f"🚫 {session_name} peer flood hatası - hesap deaktif ediliyor")
        self.deactivate_account(session_name, "Peer flood hatası")

    def reset_account_data(self):
        """Hesap verilerini sıfırla"""
        try:
            for account in self.active_accounts:
                account['message_count'] = 0
                account['last_used'] = None

            self.current_account_index = 0
            logger.info("✅ Hesap verileri sıfırlandı")

        except Exception as e:
            logger.error(f"❌ Hesap verileri sıfırlama hatası: {e}")
