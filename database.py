"""
Heroku PostgreSQL Veritabanı Yönetimi - DÜZELTILMIŞ VERSIYON
SQL hataları çözülmüş, optimized queries
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import logging
import os
from datetime import datetime
from typing import List, Tuple, Optional, Dict

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        """PostgreSQL ile bağlan ve tabloları oluştur"""
        self.db_url = os.getenv('DATABASE_URL')

        if not self.db_url:
            logger.error("❌ DATABASE_URL bulunamadı!")
            raise ValueError("DATABASE_URL gerekli!")

        # Heroku URL düzeltmesi
        if self.db_url.startswith('postgres://'):
            self.db_url = self.db_url.replace('postgres://', 'postgresql://', 1)
            logger.info("🔧 DATABASE_URL düzeltildi")

        logger.info("🗄️ PostgreSQL'e bağlanılıyor...")

        try:
            # Test connection
            test_conn = self.get_connection()
            test_conn.close()
            logger.info("✅ PostgreSQL bağlantısı başarılı!")

            # Tabloları oluştur
            self.init_database()
            logger.info("📋 PostgreSQL tabloları hazırlandı!")

        except psycopg2.Error as e:
            logger.error(f"❌ PostgreSQL bağlantı hatası: {e}")
            logger.error(f"❌ Error code: {e.pgcode}")
            logger.error(f"❌ Error details: {e.pgerror}")
            raise
        except Exception as e:
            logger.error(f"❌ PostgreSQL başlatma hatası: {type(e).__name__}: {str(e)}")
            raise

    def get_connection(self):
        """PostgreSQL bağlantısı al"""
        try:
            conn = psycopg2.connect(
                self.db_url,
                cursor_factory=RealDictCursor,
                connect_timeout=30,
                sslmode='require'
            )
            return conn
        except psycopg2.OperationalError as e:
            logger.error(f"❌ PostgreSQL connection error: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Database connection failed: {type(e).__name__}: {str(e)}")
            raise

    def init_database(self):
        """PostgreSQL tablolarını oluştur"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    # 1. Hesaplar tablosu
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS accounts (
                            id SERIAL PRIMARY KEY,
                            phone_number VARCHAR(50) UNIQUE NOT NULL,
                            session_name VARCHAR(100) NOT NULL,
                            is_active BOOLEAN DEFAULT TRUE,
                            last_used TIMESTAMP,
                            message_count INTEGER DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')

                    # 2. Aktif üyeler tablosu
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS active_members (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT UNIQUE NOT NULL,
                            username VARCHAR(100),
                            first_name VARCHAR(100),
                            last_name VARCHAR(100),
                            phone VARCHAR(50),
                            is_bot BOOLEAN DEFAULT FALSE,
                            is_admin BOOLEAN DEFAULT FALSE,
                            group_id BIGINT NOT NULL,
                            group_title VARCHAR(200),
                            message_date TIMESTAMP,
                            is_active BOOLEAN DEFAULT TRUE,
                            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')

                    # 3. Grup üyeleri tablosu
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS group_members (
                            id SERIAL PRIMARY KEY,
                            user_id BIGINT NOT NULL,
                            username VARCHAR(100),
                            first_name VARCHAR(100),
                            last_name VARCHAR(100),
                            phone VARCHAR(50),
                            is_bot BOOLEAN DEFAULT FALSE,
                            is_admin BOOLEAN DEFAULT FALSE,
                            group_id BIGINT NOT NULL,
                            group_title VARCHAR(200),
                            collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE(user_id, group_id)
                        )
                    ''')

                    # 4. Gönderilen mesajlar tablosu
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS sent_messages (
                            id SERIAL PRIMARY KEY,
                            sender_account_id INTEGER,
                            target_user_id BIGINT UNIQUE NOT NULL,
                            message_text TEXT NOT NULL,
                            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            success BOOLEAN DEFAULT TRUE,
                            error_message TEXT
                        )
                    ''')

                    # 5. Başarısız işlemler tablosu
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS failed_operations (
                            id SERIAL PRIMARY KEY,
                            operation_type VARCHAR(50) NOT NULL,
                            account_id INTEGER,
                            target_user_id BIGINT,
                            error_message TEXT,
                            retry_count INTEGER DEFAULT 0,
                            failed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        )
                    ''')

                    # İndeksler
                    cursor.execute('''
                        CREATE INDEX IF NOT EXISTS idx_active_members_user_id ON active_members(user_id);
                        CREATE INDEX IF NOT EXISTS idx_sent_messages_target_user ON sent_messages(target_user_id);
                        CREATE INDEX IF NOT EXISTS idx_sent_messages_sent_at ON sent_messages(sent_at);
                    ''')

                    conn.commit()
                    logger.info("✅ PostgreSQL tabloları oluşturuldu")

        except psycopg2.Error as e:
            logger.error(f"❌ Tablo oluşturma hatası: {e}")
            logger.error(f"❌ SQL Error code: {e.pgcode}")
            raise
        except Exception as e:
            logger.error(f"❌ Database init error: {type(e).__name__}: {str(e)}")
            raise

    def add_account(self, phone_number: str, session_name: str) -> Optional[int]:
        """Hesap ekle"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO accounts (phone_number, session_name)
                        VALUES (%s, %s)
                        ON CONFLICT (phone_number)
                        DO UPDATE SET session_name = EXCLUDED.session_name
                        RETURNING id
                    ''', (phone_number, session_name))

                    result = cursor.fetchone()
                    conn.commit()
                    return result['id'] if result else None
        except Exception as e:
            logger.error(f"Account ekleme hatası: {e}")
            return 1

    def add_active_member(self, member_data: dict):
        """Aktif üye ekle - GEÇERLİLİK KONTROLÜ İLE"""
        try:
            # Güvenlik kontrolü
            user_id = member_data.get('user_id')
            if not user_id or not isinstance(user_id, int) or user_id <= 0:
                logger.debug(f"Geçersiz user_id: {user_id}")
                return

            if user_id >= 9999999999999999999:  # Çok büyük ID'ler
                logger.debug(f"Çok büyük user_id: {user_id}")
                return

            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO active_members
                        (user_id, username, first_name, last_name, phone, is_bot, is_admin,
                         group_id, group_title, message_date, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (user_id)
                        DO UPDATE SET
                            group_id = EXCLUDED.group_id,
                            group_title = EXCLUDED.group_title,
                            message_date = EXCLUDED.message_date,
                            is_active = TRUE,
                            collected_at = CURRENT_TIMESTAMP
                    ''', (
                        user_id,
                        member_data.get('username'),
                        member_data.get('first_name'),
                        member_data.get('last_name'),
                        member_data.get('phone'),
                        member_data.get('is_bot', False),
                        member_data.get('is_admin', False),
                        member_data['group_id'],
                        member_data.get('group_title'),
                        member_data.get('message_date'),
                        member_data.get('is_active', True)
                    ))
                    conn.commit()
        except Exception as e:
            logger.debug(f"Aktif üye ekleme hatası: {e}")

    def add_group_members(self, members_data: List[dict]):
        """Grup üyelerini toplu ekle"""
        if not members_data:
            return

        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    for member in members_data:
                        cursor.execute('''
                            INSERT INTO group_members
                            (user_id, username, first_name, last_name, phone, is_bot, is_admin, group_id, group_title)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (user_id, group_id) DO NOTHING
                        ''', (
                            member['user_id'],
                            member.get('username'),
                            member.get('first_name'),
                            member.get('last_name'),
                            member.get('phone'),
                            member.get('is_bot', False),
                            member.get('is_admin', False),
                            member['group_id'],
                            member.get('group_title')
                        ))
                    conn.commit()
                    logger.info(f"✅ {len(members_data)} grup üyesi eklendi")
        except Exception as e:
            logger.error(f"Grup üyeleri ekleme hatası: {e}")

    def get_uncontacted_members(self, limit: int = None, source: str = "both") -> List[Tuple]:
        """
        Henüz mesaj gönderilmemiş üyeleri getir - DÜZELTILMIŞ SQL
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    if source == "active":
                        # Sadece aktif üyeler
                        query = '''
                            SELECT am.user_id, am.username, am.first_name, am.last_name
                            FROM active_members am
                            LEFT JOIN sent_messages sm ON am.user_id = sm.target_user_id
                            WHERE sm.target_user_id IS NULL
                            AND am.is_bot = FALSE
                            AND am.is_admin = FALSE
                            AND am.is_active = TRUE
                            AND am.user_id IS NOT NULL
                            AND am.user_id > 0
                            AND am.user_id < 9999999999999999999
                            ORDER BY am.message_date DESC NULLS LAST
                        '''
                    elif source == "static":
                        # Sadece static grup üyeleri
                        query = '''
                            SELECT gm.user_id, gm.username, gm.first_name, gm.last_name
                            FROM group_members gm
                            LEFT JOIN sent_messages sm ON gm.user_id = sm.target_user_id
                            WHERE sm.target_user_id IS NULL
                            AND gm.is_bot = FALSE
                            AND gm.is_admin = FALSE
                            AND gm.user_id IS NOT NULL
                            AND gm.user_id > 0
                            AND gm.user_id < 9999999999999999999
                            ORDER BY gm.collected_at DESC
                        '''
                    else:
                        # DÜZELTILMIŞ: Her iki kaynaktan da
                        query = '''
                            SELECT user_id, username, first_name, last_name
                            FROM (
                                SELECT am.user_id, am.username, am.first_name, am.last_name, 1 as priority
                                FROM active_members am
                                LEFT JOIN sent_messages sm ON am.user_id = sm.target_user_id
                                WHERE sm.target_user_id IS NULL
                                AND am.is_bot = FALSE
                                AND am.is_admin = FALSE
                                AND am.is_active = TRUE
                                AND am.user_id IS NOT NULL
                                AND am.user_id > 0
                                AND am.user_id < 9999999999999999999

                                UNION

                                SELECT gm.user_id, gm.username, gm.first_name, gm.last_name, 2 as priority
                                FROM group_members gm
                                LEFT JOIN sent_messages sm ON gm.user_id = sm.target_user_id
                                WHERE sm.target_user_id IS NULL
                                AND gm.is_bot = FALSE
                                AND gm.is_admin = FALSE
                                AND gm.user_id IS NOT NULL
                                AND gm.user_id > 0
                                AND gm.user_id < 9999999999999999999
                            ) combined
                            ORDER BY priority ASC, user_id ASC
                        '''

                    if limit:
                        query += f' LIMIT {limit}'

                    cursor.execute(query)
                    results = cursor.fetchall()

                    # Ek güvenlik kontrolü
                    filtered_results = []
                    for row in results:
                        user_id = row['user_id']
                        if user_id and isinstance(user_id, int) and 0 < user_id < 9999999999999999999:
                            filtered_results.append((user_id, row['username'], row['first_name'], row['last_name']))

                    logger.info(f"📊 Güvenli filtre: {len(results)} -> {len(filtered_results)} geçerli hedef")
                    return filtered_results

        except Exception as e:
            logger.error(f"Hedef üye getirme hatası: {e}")
            return []

    def log_sent_message(self, sender_account_id: int, target_user_id: int,
                        message_text: str, success: bool = True, error_message: str = None):
        """Gönderilen mesajı kaydet"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO sent_messages
                        (sender_account_id, target_user_id, message_text, success, error_message)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (target_user_id) DO NOTHING
                    ''', (sender_account_id, target_user_id, message_text, success, error_message))
                    conn.commit()
        except Exception as e:
            logger.debug(f"Mesaj kaydetme hatası: {e}")

    def get_statistics(self) -> dict:
        """İstatistikleri getir - DÜZELTILMIŞ"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    stats = {}

                    # Toplam hesap sayısı
                    cursor.execute('SELECT COUNT(*) as count FROM accounts WHERE is_active = TRUE')
                    result = cursor.fetchone()
                    stats['active_accounts'] = result['count'] if result else 0

                    # Toplam static üye sayısı
                    cursor.execute('SELECT COUNT(*) as count FROM group_members WHERE is_bot = FALSE AND is_admin = FALSE')
                    result = cursor.fetchone()
                    stats['static_members'] = result['count'] if result else 0

                    # Toplam aktif üye sayısı
                    cursor.execute('SELECT COUNT(*) as count FROM active_members WHERE is_bot = FALSE AND is_admin = FALSE AND is_active = TRUE')
                    result = cursor.fetchone()
                    stats['active_members'] = result['count'] if result else 0

                    # Gönderilen mesaj sayısı
                    cursor.execute('SELECT COUNT(*) as count FROM sent_messages WHERE success = TRUE')
                    result = cursor.fetchone()
                    stats['sent_messages'] = result['count'] if result else 0

                    # Kalan hedef sayısı - DÜZELTILMIŞ SORGU
                    cursor.execute('''
                        SELECT COUNT(DISTINCT user_id) as count FROM (
                            SELECT am.user_id FROM active_members am
                            LEFT JOIN sent_messages sm ON am.user_id = sm.target_user_id
                            WHERE sm.target_user_id IS NULL
                            AND am.is_bot = FALSE AND am.is_admin = FALSE AND am.is_active = TRUE

                            UNION

                            SELECT gm.user_id FROM group_members gm
                            LEFT JOIN sent_messages sm ON gm.user_id = sm.target_user_id
                            WHERE sm.target_user_id IS NULL
                            AND gm.is_bot = FALSE AND gm.is_admin = FALSE
                        ) combined
                    ''')
                    result = cursor.fetchone()
                    stats['remaining_members'] = result['count'] if result else 0

                    # Toplam benzersiz üye
                    stats['total_unique_members'] = stats['active_members'] + stats['static_members']
                    stats['total_members'] = stats['total_unique_members']
                    stats['remaining_active_members'] = 0
                    stats['remaining_static_members'] = 0

                    return stats
        except Exception as e:
            logger.error(f"İstatistik hatası: {e}")
            return {
                'active_accounts': 0, 'static_members': 0, 'active_members': 0,
                'total_unique_members': 0, 'total_members': 0, 'sent_messages': 0,
                'remaining_members': 0, 'remaining_active_members': 0, 'remaining_static_members': 0
            }

    def get_session_stats(self) -> dict:
        """Günlük istatistikler - DÜZELTILMIŞ"""
        stats = self.get_statistics()
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('''
                        SELECT COUNT(*) as count FROM sent_messages
                        WHERE DATE(sent_at) = CURRENT_DATE AND success = TRUE
                    ''')
                    result = cursor.fetchone()
                    messages_today = result['count'] if result else 0

                    return {
                        **stats,
                        'messages_today': messages_today,
                        'new_members_today': 0,
                        'failed_today': 0,
                        'success_rate_today': 100
                    }
        except Exception as e:
            logger.error(f"Session stats hatası: {e}")
            return {**stats, 'messages_today': 0, 'new_members_today': 0, 'failed_today': 0, 'success_rate_today': 0}

    def reset_all_data(self):
        """Tüm verileri sıfırla"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('DELETE FROM sent_messages')
                    cursor.execute('DELETE FROM active_members')
                    cursor.execute('DELETE FROM group_members')
                    cursor.execute('DELETE FROM failed_operations')
                    cursor.execute('UPDATE accounts SET message_count = 0, last_used = NULL')
                    conn.commit()
                    logger.info("✅ PostgreSQL veriler sıfırlandı")
        except Exception as e:
            logger.error(f"Veri sıfırlama hatası: {e}")

    def reset_sent_messages_only(self):
        """Sadece gönderilen mesajları sıfırla"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('DELETE FROM sent_messages')
                    cursor.execute('UPDATE accounts SET message_count = 0')
                    conn.commit()
                    logger.info("✅ PostgreSQL mesaj kayıtları sıfırlandı")
        except Exception as e:
            logger.error(f"Mesaj sıfırlama hatası: {e}")

    def get_heroku_database_info(self) -> dict:
        """PostgreSQL bilgilerini getir"""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    info = {}

                    cursor.execute("SELECT version()")
                    result = cursor.fetchone()
                    info['version'] = result[0] if result else "Unknown"

                    cursor.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
                    result = cursor.fetchone()
                    info['database_size'] = result[0] if result else "Unknown"

                    tables = ['accounts', 'active_members', 'group_members', 'sent_messages']
                    info['table_counts'] = {}

                    for table in tables:
                        cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                        result = cursor.fetchone()
                        info['table_counts'][table] = result['count'] if result else 0

                    return info
        except Exception as e:
            logger.error(f"Database info hatası: {e}")
            return {}

    # Uyumluluk için
    def clear_sent_messages(self):
        self.reset_sent_messages_only()

    def clear_group_members(self):
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('DELETE FROM group_members')
                    conn.commit()
        except Exception as e:
            logger.error(f"Grup üyeleri silme hatası: {e}")

    def clear_active_members(self):
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute('DELETE FROM active_members')
                    conn.commit()
        except Exception as e:
            logger.error(f"Aktif üyeler silme hatası: {e}")
