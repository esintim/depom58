import sqlite3
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from loguru import logger
from config import config

class Database:
    def __init__(self, db_path: str = config.DB_PATH):
        self.db_path = db_path
        self.init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def init_db(self):
        """Emlak ilan ve fiyat takip tablosunu oluşturur."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS seen_listings (
                        listing_id TEXT PRIMARY KEY,
                        city TEXT,
                        district TEXT,
                        neighborhood TEXT,
                        room_count TEXT,
                        m2 INTEGER,
                        current_price REAL,
                        previous_price REAL,
                        initial_price REAL,
                        title TEXT,
                        url TEXT,
                        image_url TEXT,
                        first_seen_at TIMESTAMP,
                        last_checked_at TIMESTAMP,
                        last_price_change_at TIMESTAMP,
                        price_change_count INTEGER DEFAULT 0
                    )
                """)
                conn.commit()
            logger.info(f"SQLite Sahibinden Emlak veritabanı hazır: {self.db_path}")
        except Exception as e:
            logger.error(f"Veritabanı başlatma hatası: {e}")

    def process_listing(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        İlanı kontrol eder:
        1. Yeni ilan ise -> veritabanına kaydeder ve 'NEW' statüsü döner.
        2. Önceden var olan ilanda FİYAT DÜŞMÜŞSE -> günceller ve 'PRICE_DROP' statüsü döner.
        3. Fiyat aynı veya artmışsa -> sadece son görülme tarihini günceller ve None döner.
        """
        try:
            listing_id = str(item["listing_id"]).strip()
            new_price = float(item["price"])
            now = datetime.now().isoformat()

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT current_price, previous_price, initial_price 
                    FROM seen_listings 
                    WHERE listing_id = ?
                """, (listing_id,))
                row = cursor.fetchone()

                # Durum 1: YENİ İLAN
                if not row:
                    cursor.execute("""
                        INSERT INTO seen_listings (
                            listing_id, city, district, neighborhood, room_count, m2,
                            current_price, previous_price, initial_price, title, url, image_url,
                            first_seen_at, last_checked_at, last_price_change_at, price_change_count
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """, (
                        listing_id,
                        item.get("city", "Mersin"),
                        item.get("district", ""),
                        item.get("neighborhood", ""),
                        item.get("room_count", ""),
                        item.get("m2", 0),
                        new_price,
                        new_price,
                        new_price,
                        item.get("title", ""),
                        item.get("url", ""),
                        item.get("image_url", ""),
                        now,
                        now,
                        now
                    ))
                    conn.commit()
                    return {
                        "type": "NEW",
                        "listing": item
                    }

                current_db_price = row[0]

                # Durum 2: FİYAT DÜŞTÜ (İNDİRİM)
                if new_price < (current_db_price - 1000.0): # En az 1000 TL düşüş
                    drop_amount = current_db_price - new_price
                    drop_rate = round((drop_amount / current_db_price) * 100, 1)

                    cursor.execute("""
                        UPDATE seen_listings SET
                            previous_price = current_price,
                            current_price = ?,
                            last_checked_at = ?,
                            last_price_change_at = ?,
                            price_change_count = price_change_count + 1
                        WHERE listing_id = ?
                    """, (new_price, now, now, listing_id))
                    conn.commit()

                    return {
                        "type": "PRICE_DROP",
                        "old_price": current_db_price,
                        "new_price": new_price,
                        "drop_amount": drop_amount,
                        "drop_rate": drop_rate,
                        "listing": item
                    }

                # Durum 3: Fiyat Değişmedi
                cursor.execute("""
                    UPDATE seen_listings SET last_checked_at = ? WHERE listing_id = ?
                """, (now, listing_id))
                conn.commit()
                return None

        except Exception as e:
            logger.error(f"Veritabanı işlem hatası ({item.get('listing_id')}): {e}")
            return None

db = Database()


