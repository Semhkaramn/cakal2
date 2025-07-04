"""
Telegram Hesap Yönetimi
Session dosyalarını otomatik algılar ve yönetir - DÜZELTILMIŞ VERSİYON
"""

import os
import glob
import logging
import asyncio
from typing import List, Dict, Optional, Union, Any
from telethon import TelegramClient
from telethon.errors import (
    SessionPasswordNeededError, FloodWaitError, PeerFloodError,
    AuthKeyDuplicatedError, PhoneNumberInvalidError, RPCError
)
import config

logger = logging.getLogger(__name__)

class AccountManager:
    def __init__(self):
        self.clients: Dict[str, TelegramClient] = {}
        self.session_files: List[str] = []
        self.active_accounts: List[Dict[str, Any]] = []
        self.current_account_index: int = 0

    def discover_session_files(self) -> List[str]:
        """Session dosyalarını otomatik olarak bul"""
        session_patterns = [
            "*.session",
            "hesap*.session",
            "account*.session"
        ]

        session_files = []
        for pattern in session_patterns:
            found_files = glob.glob(pattern)
            session_files.extend(found_files)

        # Benzersiz dosyaları al ve sırala
        unique_files = sorted(list(set(session_files)))
        logger.info(f"Bulunan session dosyaları: {unique_files}")

        # Session dosyalarının varlığını kontrol et
        valid_files = []
        for file_path in unique_files:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                valid_files.append(file_path)
            else:
                logger.warning(f"Geçersiz session dosyası: {file_path}")

        return valid_files

    async def initialize_clients(self) -> bool:
        """Her hesap için ayrı API bilgileriyle client'ları başlat"""
        logger.info("🔄 Hesaplar başlatılıyor...")

        success_count = 0

        # 1. Collector hesabını başlat
        if await self.initialize_collector():
            success_count += 1

        # 2. Sender hesaplarını başlat
        sender_success = await self.initialize_senders()
        success_count += sender_success

        if success_count == 0:
            logger.error("❌ Hiçbir hesap başlatılamadı!")
            return False

        logger.info(f"✅ Toplam {len(self.active_accounts)} hesap başlatıldı")
        return True

    async def initialize_collector(self) -> bool:
        """Collector hesabını başlat"""
        try:
            if not self._validate_collector_config():
                return False

            session_name = config.COLLECTOR_SESSION
            api_id = config.COLLECTOR_API_ID
            api_hash = config.COLLECTOR_API_HASH

            logger.info(f"📡 Collector başlatılıyor: {session_name}")

            client = TelegramClient(session_name, api_id, api_hash)

            if not await self._connect_and_authorize_client(client, session_name):
                return False

            try:
                me = await client.get_me()
                if not me:
                    logger.error(f"❌ Collector kullanıcı bilgisi alınamadı: {session_name}")
                    await client.disconnect()
                    return False

                # Collector hesabını kaydet
                account_info = {
                    'session_name': session_name,
                    'phone': getattr(me, 'phone', 'Unknown'),
                    'name': f"{getattr(me, 'first_name', '')} {getattr(me, 'last_name', '')}".strip() or 'Unknown',
                    'username': getattr(me, 'username', None),
                    'client': client,
                    'message_count': 0,
                    'is_active': True,
                    'role': 'collector',
                    'api_id': api_id,
                    'api_hash': api_hash,
                    'id': getattr(me, 'id', 0)
                }

                self.clients[session_name] = client
                self.active_accounts.append(account_info)

                logger.info(f"✅ Collector başarılı: {account_info['phone']} - {account_info['name']}")
                return True

            except Exception as e:
                logger.error(f"❌ Collector kullanıcı bilgisi hatası: {str(e)}")
                await client.disconnect()
                return False

        except Exception as e:
            logger.error(f"❌ Collector başlatılamadı: {str(e)}")
            return False

    def _validate_collector_config(self) -> bool:
        """Collector konfigürasyonunu doğrula"""
        if not config.COLLECTOR_API_ID or config.COLLECTOR_API_ID == 0:
            logger.error("❌ COLLECTOR_API_ID geçersiz")
            return False

        if not config.COLLECTOR_API_HASH:
            logger.error("❌ COLLECTOR_API_HASH boş")
            return False

        if not config.COLLECTOR_SESSION:
            logger.error("❌ COLLECTOR_SESSION boş")
            return False

        return True

    async def initialize_senders(self) -> int:
        """Sender hesaplarını başlat"""
        if not config.SENDER_ACCOUNTS:
            logger.warning("⚠️ Hiç sender hesabı tanımlanmamış")
            return 0

        sender_success_count = 0

        for sender_config in config.SENDER_ACCOUNTS:
            try:
                if not self._validate_sender_config(sender_config):
                    continue

                session_name = sender_config['session_name']
                api_id = sender_config['api_id']
                api_hash = sender_config['api_hash']
                sender_num = sender_config['number']

                logger.info(f"📤 Sender{sender_num} başlatılıyor: {session_name}")

                client = TelegramClient(session_name, api_id, api_hash)

                if not await self._connect_and_authorize_client(client, session_name):
                    continue

                try:
                    me = await client.get_me()
                    if not me:
                        logger.warning(f"❌ Sender{sender_num} kullanıcı bilgisi alınamadı")
                        await client.disconnect()
                        continue

                    # Sender hesabını kaydet
                    account_info = {
                        'session_name': session_name,
                        'phone': getattr(me, 'phone', 'Unknown'),
                        'name': f"{getattr(me, 'first_name', '')} {getattr(me, 'last_name', '')}".strip() or 'Unknown',
                        'username': getattr(me, 'username', None),
                        'client': client,
                        'message_count': 0,
                        'is_active': True,
                        'role': 'sender',
                        'sender_number': sender_num,
                        'api_id': api_id,
                        'api_hash': api_hash,
                        'id': getattr(me, 'id', 0)
                    }

                    self.clients[session_name] = client
                    self.active_accounts.append(account_info)

                    logger.info(f"✅ Sender{sender_num} başarılı: {account_info['phone']} - {account_info['name']}")
                    sender_success_count += 1

                except Exception as e:
                    logger.error(f"❌ Sender{sender_num} kullanıcı bilgisi hatası: {str(e)}")
                    await client.disconnect()
                    continue

            except Exception as e:
                logger.error(f"❌ Sender{sender_config.get('number', '?')} başlatılamadı: {str(e)}")
                continue

        logger.info(f"📊 {sender_success_count}/{len(config.SENDER_ACCOUNTS)} sender hesabı başarılı")
        return sender_success_count

    def _validate_sender_config(self, sender_config: Dict[str, Any]) -> bool:
        """Sender konfigürasyonunu doğrula"""
        required_fields = ['api_id', 'api_hash', 'session_name', 'number']

        for field in required_fields:
            if field not in sender_config or not sender_config[field]:
                logger.error(f"❌ Sender config eksik alan: {field}")
                return False

        if sender_config['api_id'] == 0:
            logger.error(f"❌ Sender{sender_config['number']} API_ID geçersiz")
            return False

        return True

    async def _connect_and_authorize_client(self, client: TelegramClient, session_name: str) -> bool:
        """Client'ı bağla ve yetkilendir"""
        try:
            await client.connect()

            if not await client.is_user_authorized():
                logger.error(f"❌ {session_name} yetkilendirilmemiş")
                await client.disconnect()
                return False

            return True

        except AuthKeyDuplicatedError:
            logger.error(f"❌ {session_name} auth key duplicate hatası")
            return False
        except PhoneNumberInvalidError:
            logger.error(f"❌ {session_name} geçersiz telefon numarası")
            return False
        except SessionPasswordNeededError:
            logger.error(f"❌ {session_name} 2FA şifresi gerekli")
            return False
        except Exception as e:
            logger.error(f"❌ {session_name} bağlantı hatası: {str(e)}")
            return False

    def get_next_account(self) -> Optional[Dict[str, Any]]:
        """Sıradaki SENDER hesabını al (collector hariç)"""
        if not self.active_accounts:
            return None

        # Sadece sender hesaplarını filtrele
        sender_accounts = [acc for acc in self.active_accounts
                          if acc.get('role') == 'sender' and acc['is_active']]

        if not sender_accounts:
            logger.warning("❌ Aktif sender hesabı bulunamadı!")
            return None

        # En az mesaj gönderen sender hesabını bul
        try:
            account = min(sender_accounts, key=lambda x: x.get('message_count', 0))
            return account
        except (ValueError, KeyError) as e:
            logger.error(f"❌ Sender hesabı seçim hatası: {e}")
            return None

    def deactivate_account(self, session_name: str, reason: str = ""):
        """Hesabı deaktif et"""
        for account in self.active_accounts:
            if account['session_name'] == session_name:
                account['is_active'] = False
                logger.warning(f"🔒 {session_name} deaktif edildi: {reason}")
                break

    def reactivate_account(self, session_name: str):
        """Hesabı yeniden aktif et"""
        for account in self.active_accounts:
            if account['session_name'] == session_name:
                account['is_active'] = True
                logger.info(f"🔓 {session_name} yeniden aktif edildi")
                break

    def increment_message_count(self, session_name: str):
        """Hesabın mesaj sayısını artır"""
        for account in self.active_accounts:
            if account['session_name'] == session_name:
                account['message_count'] = account.get('message_count', 0) + 1
                break

    async def test_account(self, session_name: str) -> bool:
        """Hesabın çalışır durumda olup olmadığını test et"""
        try:
            if session_name not in self.clients:
                logger.error(f"❌ {session_name} client bulunamadı")
                return False

            client = self.clients[session_name]

            # Bağlantıyı test et
            if not client.is_connected():
                await client.connect()

            # Kullanıcı bilgilerini al
            me = await client.get_me()
            if me:
                logger.debug(f"✅ {session_name} test başarılı")
                return True
            else:
                logger.error(f"❌ {session_name} kullanıcı bilgisi alınamadı")
                self.deactivate_account(session_name, "Test başarısız: Kullanıcı bilgisi yok")
                return False

        except Exception as e:
            logger.error(f"❌ {session_name} test başarısız: {str(e)}")
            self.deactivate_account(session_name, f"Test başarısız: {str(e)}")
            return False

    def get_account_stats(self) -> Dict[str, Union[int, List[Dict[str, Any]]]]:
        """Hesap istatistiklerini getir"""
        try:
            total_accounts = len(self.active_accounts)
            active_count = sum(1 for acc in self.active_accounts if acc.get('is_active', False))
            total_messages = sum(acc.get('message_count', 0) for acc in self.active_accounts)

            return {
                'total_accounts': total_accounts,
                'active_accounts': active_count,
                'inactive_accounts': total_accounts - active_count,
                'total_messages_sent': total_messages,
                'accounts': self.active_accounts.copy()  # Copy to prevent external modification
            }
        except Exception as e:
            logger.error(f"❌ Account stats hatası: {e}")
            return {
                'total_accounts': 0,
                'active_accounts': 0,
                'inactive_accounts': 0,
                'total_messages_sent': 0,
                'accounts': []
            }

    async def disconnect_all(self):
        """Tüm client'ları disconnect et"""
        disconnect_count = 0
        for session_name, client in self.clients.items():
            try:
                if client.is_connected():
                    await client.disconnect()
                    disconnect_count += 1
                    logger.debug(f"🔌 {session_name} disconnect edildi")
            except Exception as e:
                logger.error(f"❌ {session_name} disconnect hatası: {e}")

        self.clients.clear()
        logger.info(f"🔌 {disconnect_count} hesap disconnect edildi")

    def get_active_client(self, session_name: str) -> Optional[TelegramClient]:
        """Aktif client'ı getir"""
        client = self.clients.get(session_name)
        if client and client.is_connected():
            return client
        elif client:
            logger.warning(f"⚠️ {session_name} client bağlı değil")
        return client  # Return even if not connected, caller can handle reconnection

    async def handle_flood_wait(self, session_name: str, seconds: int):
        """Flood wait hatası yönetimi"""
        logger.warning(f"⏳ {session_name} için {seconds} saniye flood wait")

        # Eğer çok uzun süreli ise hesabı geçici olarak deaktif et
        if seconds > 300:  # 5 dakikadan fazla
            self.deactivate_account(session_name, f"Uzun flood wait: {seconds}s")
            logger.info(f"🔒 {session_name} uzun flood wait nedeniyle deaktif edildi")
        else:
            # Kısa süreli ise bekle
            logger.info(f"⏳ {session_name} için {seconds} saniye bekleniyor...")
            await asyncio.sleep(seconds)

            # Bekleme sonrası hesabı yeniden aktif et (eğer deaktifse)
            self.reactivate_account(session_name)

    async def handle_peer_flood(self, session_name: str):
        """Peer flood hatası yönetimi"""
        logger.error(f"🚫 {session_name} peer flood hatası - hesap deaktif ediliyor")
        self.deactivate_account(session_name, "Peer flood hatası")

        # Peer flood durumunda hesabı daha uzun süre deaktif tut
        await asyncio.sleep(3600)  # 1 saat bekle

        # Test et ve başarılıysa yeniden aktif et
        if await self.test_account(session_name):
            self.reactivate_account(session_name)

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

    def get_collector_client(self) -> Optional[TelegramClient]:
        """Collector client'ını getir"""
        for account in self.active_accounts:
            if account.get('role') == 'collector' and account.get('is_active'):
                return self.get_active_client(account['session_name'])
        return None

    def get_sender_clients(self) -> List[TelegramClient]:
        """Tüm aktif sender client'larını getir"""
        sender_clients = []
        for account in self.active_accounts:
            if account.get('role') == 'sender' and account.get('is_active'):
                client = self.get_active_client(account['session_name'])
                if client:
                    sender_clients.append(client)
        return sender_clients

    async def check_all_accounts_health(self) -> Dict[str, bool]:
        """Tüm hesapların sağlığını kontrol et"""
        health_status = {}

        for account in self.active_accounts:
            session_name = account['session_name']
            try:
                is_healthy = await self.test_account(session_name)
                health_status[session_name] = is_healthy
            except Exception as e:
                logger.error(f"❌ {session_name} sağlık kontrolü hatası: {e}")
                health_status[session_name] = False

        healthy_count = sum(1 for status in health_status.values() if status)
        total_count = len(health_status)

        logger.info(f"💊 Hesap sağlık kontrolü: {healthy_count}/{total_count} sağlıklı")
        return health_status

    def get_account_by_role(self, role: str) -> List[Dict[str, Any]]:
        """Role göre hesapları getir"""
        return [acc for acc in self.active_accounts if acc.get('role') == role]
