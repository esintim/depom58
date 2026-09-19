# 🏢 Mersin Emlak (Erdemli & Silifke) Fırsat ve Fiyat Takip Botu

Mersin ili **Erdemli** ve **Silifke** ilçelerinde yer alan **1+1 ve 2+1** (maksimum 2.000.000 TL) satılık daireleri sürekli tarayan, yeni eklenen ilanları ve **fiyatında indirim olan daireleri** anlık olarak **WhatsApp Grubuna** ve **Telegram Kanalına** fotoğraflı ve detaylı olarak bildiren 7/24 otonom takip botudur.

---

## 🌟 Temel Özellikler

- 📍 **Hedef Konumlar:** Mersin / Erdemli & Mersin / Silifke
- 🚪 **Oda Sayısı Filtresi:** Sadece 1+1 ve 2+1 satılık daireler
- 💰 **Bütçe Üst Sınırı:** Maksimum 2.000.000 TL
- 📱 **WhatsApp Entegrasyonu (UltraMsg):** Fotoğraflı, kalın metinli doğrudan WhatsApp grubuna anlık iletim
- 📢 **Telegram Kanalı Desteği:** Zengin HTML kartları ve ilana git butonu
- 📉 **Fiyat Düşüşü Alarmı:** Takipteki bir dairenin fiyatı indiğinde Eski Fiyat ➔ Yeni Fiyat, İndirim Miktarı (TL) ve Yüzdesi (%) ile acil uyarı
- 💾 **SQLite Anti-Spam Veritabanı:** Daha önce bildirilen ilanlar tekrar atılmaz, yalnızca yeni veya fiyatı düşenler bildirilir
- 🌐 **Render.com 7/24 Kesintisiz Çalışma:** Entegre keep-alive sunucusu ile bulutta 7/24 uyanık kalır

---

## 🚀 Kurulum ve Çalıştırma

1. Gerekli kütüphaneleri yükleyin:
```bash
pip install -r requirements.txt
```

2. `.env` dosyasını yapılandırın:
```env
MAX_PRICE=2000000
MIN_PRICE=50000
SCRAPE_INTERVAL_SECONDS=60
DB_PATH=sahibinden_emlak.db

ENABLE_TELEGRAM=true
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=@your_channel

ENABLE_WHATSAPP=true
WHATSAPP_PROVIDER=ultramsg
WHATSAPP_INSTANCE_ID=your_instance_id
WHATSAPP_TOKEN=your_token
WHATSAPP_TARGET=your_group_id@g.us
```

3. Botu başlatın:
```bash
python main.py
```

