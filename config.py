import os
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "8838254421:AAG28jZwOVSGtHNdEYvRRR15nyDhjDCMhrs")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "@amzntkp")
    
    # Hedef Şehir ve İlçeler
    LOCATIONS: List[Dict[str, str]] = [
        {
            "name": "Erdemli",
            "city": "Mersin",
            "emlakjet_url": "https://www.emlakjet.com/satilik-konut/mersin-erdemli/?fiyat=0-2000000&oda_sayisi=1+1,2+1&siralama=tarih_azalan",
            "sahibinden_url": "https://www.sahibinden.com/satilik-daire/mersin-erdemli?sorting=date_desc&price_max=2000000"
        },
        {
            "name": "Silifke",
            "city": "Mersin",
            "emlakjet_url": "https://www.emlakjet.com/satilik-konut/mersin-silifke/?fiyat=0-2000000&oda_sayisi=1+1,2+1&siralama=tarih_azalan",
            "sahibinden_url": "https://www.sahibinden.com/satilik-daire/mersin-silifke?sorting=date_desc&price_max=2000000"
        }
    ]
    
    # İzin Verilen Oda Tipleri (Sadece 1+1 ve 2+1)
    ALLOWED_ROOMS: List[str] = ["1+1", "2+1"]
    
    # Maksimum Fiyat Limiti (TL)
    MAX_PRICE: float = float(os.getenv("MAX_PRICE", "2000000"))
    
    # Minimum Fiyat Filtresi (Hatalı/Kiralık 0 TL ilanları engellemek için)
    MIN_PRICE: float = float(os.getenv("MIN_PRICE", "50000"))
    
    # Tarama Sıklığı (Saniye cinsinden)
    SCRAPE_INTERVAL_SECONDS: int = int(os.getenv("SCRAPE_INTERVAL_SECONDS", "60"))
    
    # SQLite Veritabanı Yolu
    DB_PATH: str = os.getenv("DB_PATH", "sahibinden_emlak.db")

    # WhatsApp Bildirim Ayarları (UltraMsg / Green-API)
    ENABLE_WHATSAPP: bool = os.getenv("ENABLE_WHATSAPP", "true").lower() in ("1", "true", "yes")
    ENABLE_TELEGRAM: bool = os.getenv("ENABLE_TELEGRAM", "true").lower() in ("1", "true", "yes")
    WHATSAPP_PROVIDER: str = os.getenv("WHATSAPP_PROVIDER", "ultramsg") # ultramsg veya greenapi
    WHATSAPP_INSTANCE_ID: str = os.getenv("WHATSAPP_INSTANCE_ID", "")   # Örn: instance12345
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")               # UltraMsg veya Green-API Token
    WHATSAPP_TARGET: str = os.getenv("WHATSAPP_TARGET", "")             # Örn: 905xxxxxxxxx veya 120363xxx@g.us

config = Config()




