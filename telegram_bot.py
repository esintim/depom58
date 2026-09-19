import html
from typing import Dict, Any
import httpx
from loguru import logger
from config import config

class TelegramNotifier:
    def __init__(self, bot_token: str = config.TELEGRAM_BOT_TOKEN, chat_id: str = config.TELEGRAM_CHAT_ID):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def _format_price(self, price: float) -> str:
        """Fiyatı 1.850.000 TL şeklinde biçimlendirir."""
        return f"{price:,.0f} TL".replace(",", ".")

    def format_new_listing_caption(self, item: Dict[str, Any]) -> str:
        """Yeni eklenen satılık daire ilanı için Telegram mesajı."""
        title = html.escape(item.get("title", "Satılık Daire"))
        if len(title) > 160:
            title = title[:157] + "..."

        district = item.get("district", "Erdemli / Silifke")
        neighborhood = item.get("neighborhood", "")
        room = item.get("room_count", "1+1 / 2+1")
        m2 = item.get("m2", 0)
        price_fmt = self._format_price(item.get("price", 0))
        source = item.get("source", "Emlakjet / Sahibinden")

        lines = [
            "🏠 <b>YENİ DAİRE İLANI BİLDİRİMİ</b> 🏠\n",
            f"📍 <b>Konum:</b> Mersin / <b>{district}</b> ({neighborhood})",
            f"🚪 <b>Oda Sayısı:</b> <b>{room}</b>",
            f"📐 <b>Metrekare:</b> <b>{m2} m²</b>" if m2 > 0 else "📐 <b>Metrekare:</b> <i>Belirtilmemiş</i>",
            f"💰 <b>Fiyat:</b> <b>{price_fmt}</b>\n",
            f"📌 <b>Başlık:</b> {title}\n",
            f"🌐 <b>Kaynak:</b> {source} (Mersin {district})"
        ]
        return "\n".join(lines)

    def format_price_drop_caption(self, event: Dict[str, Any]) -> str:
        """Fiyatı düşen daire için acil indirim alarmı mesajı."""
        item = event.get("listing", {})
        title = html.escape(item.get("title", "Satılık Daire"))
        if len(title) > 160:
            title = title[:157] + "..."

        district = item.get("district", "Erdemli / Silifke")
        neighborhood = item.get("neighborhood", "")
        room = item.get("room_count", "1+1 / 2+1")
        m2 = item.get("m2", 0)
        source = item.get("source", "Emlakjet / Sahibinden")

        old_price_fmt = self._format_price(event.get("old_price", 0))
        new_price_fmt = self._format_price(event.get("new_price", 0))
        drop_fmt = self._format_price(event.get("drop_amount", 0))
        drop_rate = event.get("drop_rate", 0.0)

        lines = [
            "🚨 <b>FİYATI DÜŞEN DAİRE ALARMI!</b> 🚨\n",
            f"📉 <b>İNDİRİM:</b> <b>-{drop_fmt}</b> (%{drop_rate:.1f} Düşüş!)\n",
            f"🏷️ <b>Eski Fiyat:</b> <s>{old_price_fmt}</s>",
            f"💰 <b>YENİ FİYAT:</b> <b>{new_price_fmt}</b>\n",
            f"📍 <b>Konum:</b> Mersin / <b>{district}</b> ({neighborhood})",
            f"🚪 <b>Oda Sayısı:</b> <b>{room}</b>",
            f"📐 <b>Metrekare:</b> <b>{m2} m²</b>" if m2 > 0 else "📐 <b>Metrekare:</b> <i>Belirtilmemiş</i>",
            f"📌 <b>Başlık:</b> {title}\n",
            f"🌐 <b>Kaynak:</b> {source}"
        ]
        return "\n".join(lines)

    async def send_event_notification(self, event: Dict[str, Any], max_retries: int = 3) -> bool:
        """Etkinliği (YENİ İLAN veya FİYAT DÜŞÜŞÜ) Telegram kanalına gönderir."""
        if not self.is_configured():
            logger.warning("Telegram Bot Token veya Chat ID ayarlanmamış!")
            return False

        event_type = event.get("type")
        item = event.get("listing", {})

        if event_type == "NEW":
            caption = self.format_new_listing_caption(item)
            btn_title = "🏠 İlana Git ve İncele"
        elif event_type == "PRICE_DROP":
            caption = self.format_price_drop_caption(event)
            btn_title = "🔥 İndirimli İlana Git"
        else:
            return False

        listing_url = item.get("url", "https://t.me/amzntkp")
        image_url = item.get("image_url", "")

        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": btn_title, "url": listing_url}
                ]
            ]
        }

        async with httpx.AsyncClient(timeout=20) as client:
            for attempt in range(max_retries):
                try:
                    if image_url and image_url.startswith("http"):
                        payload = {
                            "chat_id": self.chat_id,
                            "photo": image_url,
                            "caption": caption,
                            "parse_mode": "HTML",
                            "reply_markup": reply_markup
                        }
                        resp = await client.post(f"{self.api_url}/sendPhoto", json=payload)
                    else:
                        payload = {
                            "chat_id": self.chat_id,
                            "text": caption,
                            "parse_mode": "HTML",
                            "disable_web_page_preview": False,
                            "reply_markup": reply_markup
                        }
                        resp = await client.post(f"{self.api_url}/sendMessage", json=payload)

                    if resp.status_code == 200:
                        logger.info(f"✅ Telegram bildirimi iletildi: [{event_type}] {item.get('title')[:30]}")
                        return True

                    if resp.status_code == 429:
                        data = resp.json()
                        retry_after = data.get("parameters", {}).get("retry_after", 20)
                        logger.warning(f"⏳ Telegram Flood Koruması (429): {retry_after} sn bekleniyor...")
                        await asyncio.sleep(retry_after + 2)
                        continue

                    # Resim yükleme hatası olursa metin olarak dene
                    if image_url and resp.status_code != 200:
                        logger.warning(f"Görsel gönderilemedi ({resp.status_code}), metin olarak deneniyor...")
                        payload = {
                            "chat_id": self.chat_id,
                            "text": caption,
                            "parse_mode": "HTML",
                            "disable_web_page_preview": False,
                            "reply_markup": reply_markup
                        }
                        fb_resp = await client.post(f"{self.api_url}/sendMessage", json=payload)
                        if fb_resp.status_code == 200:
                            return True

                    logger.error(f"❌ Telegram API hatası ({resp.status_code}): {resp.text}")
                    return False

                except Exception as e:
                    logger.error(f"Telegram bildirim gönderme hatası: {e}")
                    await asyncio.sleep(3)

        return False

    async def send_startup_message(self) -> bool:
        if not self.is_configured():
            return False

        text = (
            "🏢 <b>Mersin Emlak Fırsat & Fiyat Takip Botu Aktif!</b>\n\n"
            "📍 <b>Bölgeler:</b> Mersin / <b>Erdemli</b> & <b>Silifke</b>\n"
            "🚪 <b>Oda Tipleri:</b> <b>1+1</b> ve <b>2+1</b> Satılık Daireler\n"
            f"💰 <b>Üst Limit:</b> <b>{self._format_price(config.MAX_PRICE)}</b>\n\n"
            "✨ <i>Yeni eklenen daireler ve fiyatı düşen (indirimli) daireler anlık olarak bu kanala iletilecektir.</i>"
        )
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(f"{self.api_url}/sendMessage", json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML"
                })
                return True
        except Exception as e:
            logger.warning(f"Başlangıç mesajı gönderilemedi: {e}")
            return False

telegram_notifier = TelegramNotifier()



