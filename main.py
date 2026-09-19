import asyncio
import os
import sys
import threading
import httpx
from http.server import HTTPServer, BaseHTTPRequestHandler
from loguru import logger
from config import config
from scraper import scraper
from telegram_bot import telegram_notifier
from whatsapp_notifier import whatsapp_notifier

import io


# Standart terminal çıktısını UTF-8'e sabitle (Windows / Render çökmelerini %100 önler)
try:
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "buffer"):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

# Log formatlama ayarı
logger.remove()
logger.add(
    sys.stdout, 
    colorize=True, 
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>"
)
logger.add(
    "emlak_bot.log", 
    rotation="10 MB", 
    retention="7 days", 
    encoding="utf-8"
)

# Render'ın 7/24 "Live" ve uyanık kalmasını sağlayan Web Sunucusu
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Mersin (Erdemli & Silifke) Emlak & Fiyat Takip Botu 7/24 Aktif!")

    def log_message(self, format, *args):
        pass

def start_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Render Free Plan uyku modunu engellemek için kendi kendini 10 dakikada bir uyandırma döngüsü
async def keep_alive_loop():
    await asyncio.sleep(60)
    port = os.environ.get("PORT", 10000)
    while True:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.get(f"http://127.0.0.1:{port}/")
        except Exception:
            pass
        await asyncio.sleep(600)  # Her 10 dakikada bir ping at

async def run_bot():
    # Bulut sunucu port dinleyicisini arka planda başlat
    t = threading.Thread(target=start_health_server, daemon=True)
    t.start()
    logger.info(f"🌐 Bulut Web Sunucusu Port {os.environ.get('PORT', 10000)} uzerinde baslatildi.")

    # Uyanık kalma görevini başlat
    asyncio.create_task(keep_alive_loop())

    if "--reset-db" in sys.argv:
        if os.path.exists(config.DB_PATH):
            os.remove(config.DB_PATH)
            logger.warning("Veritabanı sıfırlandı.")
            from database import db
            db.init_db()

    logger.info("==================================================")
    logger.info("🏢 Mersin Emlak & Fiyat Takip Botu Başlatılıyor...")
    logger.info("📍 Hedef Bölgeler: Erdemli & Silifke")
    logger.info(f"🚪 Oda Tipleri: {', '.join(config.ALLOWED_ROOMS)}")
    logger.info(f"💰 Maksimum Bütçe Limiti: {config.MAX_PRICE:,.0f} TL")
    logger.info(f"⏱️ Tarama Sıklığı: {config.SCRAPE_INTERVAL_SECONDS} saniye")
    if config.ENABLE_TELEGRAM and config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        logger.info(f"📢 Telegram Hedef Kanal: {config.TELEGRAM_CHAT_ID}")
        await telegram_notifier.send_startup_message()
    if config.ENABLE_WHATSAPP and whatsapp_notifier.is_configured():
        logger.info(f"📱 WhatsApp Hedef: {config.WHATSAPP_TARGET} ({config.WHATSAPP_PROVIDER})")
    logger.info("==================================================")

    while True:
        try:
            logger.info("🔍 Mersin Erdemli ve Silifke'deki daireler taranıyor...")
            events = await scraper.scan_for_events()
            
            if events:
                logger.success(f"✨ {len(events)} adet YENİ olay bulundu, bildirimler iletiliyor!")
                for ev in events:
                    # 1. Telegram Gönderimi
                    if config.ENABLE_TELEGRAM and telegram_notifier.is_configured():
                        await telegram_notifier.send_event_notification(ev)
                    
                    # 2. WhatsApp Gönderimi
                    if config.ENABLE_WHATSAPP and whatsapp_notifier.is_configured():
                        await whatsapp_notifier.send_event_notification(ev)

                    await asyncio.sleep(2.5)
            else:
                logger.info("ℹ️ Bu turda yeni ilan veya fiyat düşüşü yok (mevcut ilanlar güncel).")

        except Exception as e:
            logger.error(f"❌ Döngü hatası: {e}")

        logger.info(f"⏳ Bir sonraki tarama için {config.SCRAPE_INTERVAL_SECONDS} saniye bekleniyor...\n")
        await asyncio.sleep(config.SCRAPE_INTERVAL_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Bot durduruldu.")


