"""
Telegram Mesaj Gönderici Modülü - HATA DÜZELTİLMİŞ VERSİYON
Import hatası çözülmüş, sadece mevcut error'lar kullanılıyor
"""

import logging
import asyncio
import random
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional
from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError, PeerFloodError, UserPrivacyRestrictedError,
    UserNotParticipantError, ChatWriteForbiddenError, UserBannedInChannelError,
    InputUserDeactivatedError, UserDeactivatedError
    # EntityUseError kaldırıldı - Telethon'da mevcut değil
)
from telethon.tl.types import User
import config
from database import DatabaseManager
from account_manager import AccountManager

logger = logging.getLogger(__name__)

class MessageSender:
    def __init__(self, db_manager: DatabaseManager, account_manager: AccountManager):
        self.db = db_manager
        self.account_manager = account_manager
        self.command_handler = None
        self.sending_active = True
        self.current_account = None
        self.messages_sent_today = 0
        self.session_stats = {
            'sent': 0,
            'failed': 0,
            'errors': []
        }

    def set_command_handler(self, command_handler):
        """Command handler referansını ayarla"""
        self.command_handler = command_handler

    async def send_messages_batch(self, targets: List[Tuple], batch_size: int = 20) -> Dict:
        """Hedef listesine batch halinde mesaj gönder - DÜZELTILMIŞ"""
        results = {
            'sent': 0,
            'failed': 0,
            'errors': [],
            'total_targets': len(targets)
        }

        if not targets:
            logger.info("📭 Gönderilecek hedef yok")
            return results

        logger.info(f"📤 {len(targets)} hedefe mesaj gönderimi başlıyor...")

        # Hedefleri doğrula
        valid_targets = []
        for target in targets:
            if len(target) >= 4 and target[0] and isinstance(target[0], int) and target[0] > 0:
                valid_targets.append(target)
            else:
                logger.debug(f"Geçersiz hedef atlandı: {target}")
                results['failed'] += 1

        if not valid_targets:
            logger.warning("❌ Geçerli hedef bulunamadı!")
            return results

        logger.info(f"✅ {len(valid_targets)}/{len(targets)} geçerli hedef")

        # Batch'lere böl
        for i in range(0, len(valid_targets), batch_size):
            batch = valid_targets[i:i + batch_size]

            # Sistem durumunu kontrol et
            if self.command_handler and not self.command_handler.is_sending_enabled():
                logger.info("⏸️ Mesaj gönderimi durduruldu, batch sonlandırılıyor")
                break

            logger.info(f"📦 Batch {i//batch_size + 1}: {len(batch)} hedef işleniyor...")

            # Batch'i işle
            batch_results = await self._process_batch(batch)

            # Sonuçları birleştir
            results['sent'] += batch_results['sent']
            results['failed'] += batch_results['failed']
            results['errors'].extend(batch_results['errors'])

            # Batch'ler arası bekleme
            if i + batch_size < len(valid_targets):
                delay = random.randint(10, 20)
                logger.info(f"⏳ Batch'ler arası {delay} saniye bekleme...")
                await asyncio.sleep(delay)

        logger.info(f"✅ Batch gönderim tamamlandı: {results['sent']} başarılı, {results['failed']} başarısız")
        return results

    async def _process_batch(self, batch: List[Tuple]) -> Dict:
        """Tek batch'i işle"""
        results = {'sent': 0, 'failed': 0, 'errors': []}

        for target in batch:
            try:
                # Sistem durumunu kontrol et
                if self.command_handler and not self.command_handler.is_sending_enabled():
                    logger.info("⏸️ Gönderim durduruldu")
                    break

                # Mesaj gönder
                success = await self._send_single_message(target)

                if success:
                    results['sent'] += 1
                else:
                    results['failed'] += 1

                # Mesajlar arası bekleme
                delay = random.randint(config.MESSAGE_DELAY_MIN, config.MESSAGE_DELAY_MAX)
                await asyncio.sleep(delay)

            except Exception as e:
                logger.error(f"❌ Batch işleme hatası: {str(e)}")
                results['failed'] += 1
                results['errors'].append(str(e))

        return results

    async def _send_single_message(self, target: Tuple) -> bool:
        """Tek hedefe mesaj gönder - GÜÇLENDIRILMIŞ ENTITY RESOLUTION"""
        try:
            user_id, username, first_name, last_name = target

            # ID validation
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                logger.debug(f"Geçersiz user_id: {user_id}")
                return False

            if user_id >= 9999999999999999999:  # Çok büyük ID'ler
                logger.debug(f"Çok büyük user_id: {user_id}")
                return False

            # Aktif hesap al
            account = self._get_next_sender_account()
            if not account:
                logger.error("❌ Aktif sender hesabı yok!")
                return False

            client = self.account_manager.get_active_client(account['session_name'])
            if not client:
                logger.error(f"❌ Client bulunamadı: {account['session_name']}")
                return False

            # Mesaj metnini hazırla
            message_text = self._prepare_message_text()

            # DÜZELTILMIŞ: Güçlendirilmiş entity resolution
            entity = await self._resolve_target_entity(client, user_id, username)

            if not entity:
                # Entity bulunamazsa başarısız kaydet
                self.db.log_sent_message(
                    sender_account_id=1,
                    target_user_id=user_id,
                    message_text=message_text,
                    success=False,
                    error_message="Entity not found"
                )
                logger.debug(f"Entity bulunamadı: {user_id} (@{username})")
                return False

            # Mesajı gönder
            try:
                await client.send_message(entity, message_text)

                # Başarılı gönderimi kaydet
                self.db.log_sent_message(
                    sender_account_id=1,  # Account ID
                    target_user_id=user_id,
                    message_text=message_text,
                    success=True
                )

                # İstatistikleri güncelle
                self.account_manager.increment_message_count(account['session_name'])
                self.session_stats['sent'] += 1
                self.messages_sent_today += 1

                display_name = first_name or username or f"ID:{user_id}"
                logger.info(f"✅ Mesaj gönderildi: {display_name} <- {account['phone']}")
                return True

            except FloodWaitError as e:
                logger.warning(f"⏳ Flood wait {account['session_name']}: {e.seconds}s")
                await self.account_manager.handle_flood_wait(account['session_name'], e.seconds)

                # Başarısız gönderimi kaydet
                self.db.log_sent_message(
                    sender_account_id=1,
                    target_user_id=user_id,
                    message_text=message_text,
                    success=False,
                    error_message=f"FloodWaitError: {e.seconds}s"
                )
                return False

            except PeerFloodError:
                logger.error(f"🚫 Peer flood {account['session_name']}")
                await self.account_manager.handle_peer_flood(account['session_name'])

                # Başarısız gönderimi kaydet
                self.db.log_sent_message(
                    sender_account_id=1,
                    target_user_id=user_id,
                    message_text=message_text,
                    success=False,
                    error_message="PeerFloodError"
                )
                return False

            except (UserPrivacyRestrictedError, UserNotParticipantError,
                    ChatWriteForbiddenError, UserBannedInChannelError,
                    InputUserDeactivatedError, UserDeactivatedError) as e:
                # Bu hatalar normal, kullanıcı ayarları
                logger.debug(f"Kullanıcı erişilemez {user_id}: {type(e).__name__}")

                # Başarısız gönderimi kaydet
                self.db.log_sent_message(
                    sender_account_id=1,
                    target_user_id=user_id,
                    message_text=message_text,
                    success=False,
                    error_message=type(e).__name__
                )
                return False

            except Exception as e:
                error_msg = str(e)
                logger.debug(f"Mesaj gönderimi hatası {user_id}: {error_msg}")

                # Başarısız gönderimi kaydet
                self.db.log_sent_message(
                    sender_account_id=1,
                    target_user_id=user_id,
                    message_text=message_text,
                    success=False,
                    error_message=error_msg
                )
                return False

        except Exception as e:
            logger.error(f"❌ Genel gönderim hatası: {str(e)}")
            return False

    async def _resolve_target_entity(self, client: TelegramClient, user_id: int, username: str = None):
        """Güçlendirilmiş entity resolution - Sadece mevcut yöntemlerle"""
        try:
            # Yöntem 1: Direkt user_id ile
            try:
                entity = await client.get_entity(user_id)
                if hasattr(entity, 'id') and entity.id == user_id:
                    logger.debug(f"✅ Entity bulundu (user_id): {user_id}")
                    return entity
            except ValueError:
                pass  # Devam et

            # Yöntem 2: Username ile (eğer varsa)
            if username and username.strip():
                try:
                    # @ işaretini temizle
                    clean_username = username.strip().replace('@', '')
                    entity = await client.get_entity(clean_username)
                    if hasattr(entity, 'id') and entity.id == user_id:
                        logger.debug(f"✅ Entity bulundu (username): @{clean_username}")
                        return entity
                except ValueError:
                    pass

            # Yöntem 3: Input peer ile deneme (basit versiyon)
            try:
                from telethon.tl.types import InputPeerUser

                # Bu risky ama bazen çalışır
                input_peer = InputPeerUser(user_id, 0)  # Access hash 0 ile dene
                entity = await client.get_entity(input_peer)
                if hasattr(entity, 'id') and entity.id == user_id:
                    logger.debug(f"✅ Entity bulundu (input_peer): {user_id}")
                    return entity
            except:
                pass

            # Hiçbiri çalışmazsa None döndür
            logger.debug(f"❌ Entity çözümlenemedi: {user_id} (@{username})")
            return None

        except Exception as e:
            logger.debug(f"Entity resolution error: {e}")
            return None

    def _get_next_sender_account(self) -> Optional[Dict]:
        """Sıradaki sender hesabını al"""
        return self.account_manager.get_next_account()

    def _prepare_message_text(self) -> str:
        """Mesaj metnini hazırla ve çeşitlendir"""
        base_message = config.BASE_MESSAGE

        # Basit çeşitlendirme
        if hasattr(config, 'MESSAGE_PREFIXES') and hasattr(config, 'MESSAGE_SUFFIXES'):
            prefix = random.choice(config.MESSAGE_PREFIXES)
            suffix = random.choice(config.MESSAGE_SUFFIXES)

            # %50 ihtimalle prefix ekle
            if random.random() < 0.5:
                base_message = prefix + base_message

            # %30 ihtimalle suffix ekle
            if random.random() < 0.3:
                base_message = base_message + suffix

        return base_message

    async def send_test_message(self, target_user_id: int, custom_message: str = None) -> bool:
        """Test mesajı gönder"""
        try:
            account = self._get_next_sender_account()
            if not account:
                logger.error("❌ Test için aktif hesap yok!")
                return False

            client = self.account_manager.get_active_client(account['session_name'])
            if not client:
                logger.error(f"❌ Test client bulunamadı: {account['session_name']}")
                return False

            message_text = custom_message or "Test mesajı - Telegram Messenger"

            # Entity resolution
            entity = await self._resolve_target_entity(client, target_user_id)

            if not entity:
                logger.error(f"❌ Test entity bulunamadı: {target_user_id}")
                return False

            await client.send_message(entity, message_text)
            logger.info(f"✅ Test mesajı gönderildi: {target_user_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Test mesajı hatası: {str(e)}")
            return False

    def estimate_completion_time(self) -> Dict:
        """Tamamlanma zamanını tahmin et"""
        try:
            # Kalan hedef sayısını al
            remaining_targets = self.db.get_uncontacted_members(limit=None)
            remaining_count = len(remaining_targets)

            if remaining_count == 0:
                return {
                    'remaining_messages': 0,
                    'estimated_seconds': 0,
                    'estimated_hours': 0
                }

            # Ortalama mesaj gönderim hızını hesapla
            avg_delay = (config.MESSAGE_DELAY_MIN + config.MESSAGE_DELAY_MAX) / 2
            messages_per_hour = 3600 / avg_delay  # Saniyede mesaj sayısı * 3600

            # Aktif hesap sayısını al
            active_senders = len([acc for acc in self.account_manager.active_accounts
                                if acc.get('role') == 'sender' and acc['is_active']])

            if active_senders == 0:
                active_senders = 1

            # Toplam hızı hesapla
            total_messages_per_hour = messages_per_hour * active_senders

            # Tahmini süre
            estimated_hours = remaining_count / total_messages_per_hour
            estimated_seconds = int(estimated_hours * 3600)

            return {
                'remaining_messages': remaining_count,
                'estimated_seconds': estimated_seconds,
                'estimated_hours': round(estimated_hours, 2),
                'active_senders': active_senders,
                'messages_per_hour': int(total_messages_per_hour)
            }

        except Exception as e:
            logger.error(f"❌ Süre tahmini hatası: {str(e)}")
            return {
                'remaining_messages': 0,
                'estimated_seconds': 0,
                'estimated_hours': 0
            }

    async def check_sending_limits(self) -> bool:
        """Gönderim limitlerini kontrol et"""
        try:
            # Saatlik limit kontrolü
            if self.messages_sent_today >= config.MESSAGES_PER_HOUR:
                logger.warning(f"⚠️ Saatlik limit aşıldı: {self.messages_sent_today}/{config.MESSAGES_PER_HOUR}")
                return False

            # Aktif hesap kontrolü
            active_senders = [acc for acc in self.account_manager.active_accounts
                            if acc.get('role') == 'sender' and acc['is_active']]

            if not active_senders:
                logger.warning("⚠️ Aktif sender hesabı yok!")
                return False

            return True

        except Exception as e:
            logger.error(f"❌ Limit kontrolü hatası: {str(e)}")
            return False

    def get_sender_stats(self) -> Dict:
        """Sender istatistiklerini getir"""
        try:
            db_stats = self.db.get_session_stats()

            return {
                'session_sent': self.session_stats['sent'],
                'session_failed': self.session_stats['failed'],
                'total_sent_db': db_stats['sent_messages'],
                'remaining_targets': db_stats['remaining_members'],
                'messages_today': db_stats['messages_today'],
                'active_accounts': len([acc for acc in self.account_manager.active_accounts
                                      if acc.get('role') == 'sender' and acc['is_active']]),
                'errors_count': len(self.session_stats['errors'])
            }

        except Exception as e:
            logger.error(f"❌ Sender stats hatası: {str(e)}")
            return {}

    def reset_session_stats(self):
        """Session istatistiklerini sıfırla"""
        self.session_stats = {'sent': 0, 'failed': 0, 'errors': []}
        self.messages_sent_today = 0
        logger.info("📊 Sender session stats sıfırlandı")

    async def pause_sending(self):
        """Gönderimi duraklat"""
        self.sending_active = False
        logger.info("⏸️ Mesaj gönderimi duraklatıldı")

    async def resume_sending(self):
        """Gönderimi devam ettir"""
        self.sending_active = True
        logger.info("▶️ Mesaj gönderimi devam ediyor")

    def is_sending_active(self) -> bool:
        """Gönderim aktif mi?"""
        return self.sending_active and (not self.command_handler or self.command_handler.is_sending_enabled())

    async def validate_targets_before_sending(self, targets: List[Tuple]) -> List[Tuple]:
        """Gönderim öncesi hedefleri doğrula"""
        valid_targets = []

        for target in targets:
            try:
                user_id, username, first_name, last_name = target

                # Temel validasyonlar
                if not user_id or not isinstance(user_id, int) or user_id <= 0:
                    logger.debug(f"Geçersiz user_id: {user_id}")
                    continue

                if user_id >= 9999999999999999999:
                    logger.debug(f"Çok büyük user_id: {user_id}")
                    continue

                valid_targets.append(target)

            except (ValueError, IndexError) as e:
                logger.debug(f"Target parsing hatası: {e}")
                continue

        logger.info(f"🎯 Hedef validasyonu: {len(targets)} -> {len(valid_targets)} geçerli")
        return valid_targets
