import os
import re
import httpx
from typing import Dict, Any, Optional
from loguru import logger
from config import config

class WhatsAppNotifier:
    def __init__(self):
        self.provider = getattr(config, "WHATSAPP_PROVIDER", "ultramsg").lower()
        self.instance_id = getattr(config, "WHATSAPP_INSTANCE_ID", "")
        self.token = getattr(config, "WHATSAPP_TOKEN", "")
        self.target = getattr(config, "WHATSAPP_TARGET", "")

    def is_configured(self) -> bool:
        return bool(self.instance_id and self.token and self.target)

    def _format_price(self, price: float) -> str:
        """Fiyatı 1.850.000 TL şeklinde biçimlendirir."""
        return f"{price:,.0f} TL".replace(",", ".")

    def _clean_url(self, raw_url: str) -> str:
        """İlan adresini tertemiz, kısa ve hatasız hale getirir."""
        if not raw_url:
            return ""
        # Soru işaretinden sonraki gereksiz takip kodlarını temizle
        clean = raw_url.split("?")[0].strip()
        return clean


    def format_new_listing_message(self, item: Dict[str, Any]) -> str:
        """Yeni ilan için WhatsApp mesaj metni."""
        title = item.get("title", "Satılık Daire")
        district = item.get("district", "Erdemli / Silifke")
        neighborhood = item.get("neighborhood", "")
        room = item.get("room_count", "1+1 / 2+1")
        m2 = item.get("m2", 0)
        price_fmt = self._format_price(item.get("price", 0))
        raw_url = item.get("url", "")
        clean_url = self._clean_url(raw_url)
        source = item.get("source", "Sahibinden.com")
        lid = item.get("listing_id", "").replace("SH-", "").replace("EJ-", "")

        m2_text = f"📐 *Metrekare:* {m2} m²" if m2 > 0 else "📐 *Metrekare:* Belirtilmemiş"
        id_text = f"🔢 *İlan No:* {lid}\n" if lid else ""

        lines = [
            "🏠 *YENİ DAİRE İLANI BİLDİRİMİ* 🏠",
            "",
            f"📍 *Konum:* Mersin / *{district}* ({neighborhood})",
            f"🚪 *Oda Sayısı:* *{room}*",
            m2_text,
            f"💰 *Fiyat:* *{price_fmt}*",
            "",
            f"📌 *Başlık:* {title}",
            id_text,
            f"🌐 *Kaynak:* {source}",
            "",
            "🔗 *İLAN LİNKİ:*",
            f"{clean_url}"
        ]
        return "\n".join(lines)


    def format_price_drop_message(self, event: Dict[str, Any]) -> str:
        """Fiyatı düşen daire için WhatsApp indirim alarmı mesajı."""
        item = event.get("listing", {})
        title = item.get("title", "Satılık Daire")
        district = item.get("district", "Erdemli / Silifke")
        neighborhood = item.get("neighborhood", "")
        room = item.get("room_count", "1+1 / 2+1")
        m2 = item.get("m2", 0)
        raw_url = item.get("url", "")
        clean_url = self._clean_url(raw_url)
        source = item.get("source", "Sahibinden.com")
        lid = item.get("listing_id", "").replace("SH-", "").replace("EJ-", "")

        old_price_fmt = self._format_price(event.get("old_price", 0))
        new_price_fmt = self._format_price(event.get("new_price", 0))
        drop_fmt = self._format_price(event.get("drop_amount", 0))
        drop_rate = event.get("drop_rate", 0.0)

        m2_text = f"📐 *Metrekare:* {m2} m²" if m2 > 0 else "📐 *Metrekare:* Belirtilmemiş"
        id_text = f"🔢 *İlan No:* {lid}\n" if lid else ""

        lines = [
            "🚨 *FİYATI DÜŞEN DAİRE ALARMI!* 🚨",
            "",
            f"📉 *İNDİRİM:* *-{drop_fmt}* (%{drop_rate:.1f} Düşüş!)",
            f"🏷️ *Eski Fiyat:* ~{old_price_fmt}~",
            f"💰 *YENİ FİYAT:* *{new_price_fmt}*",
            "",
            f"📍 *Konum:* Mersin / *{district}* ({neighborhood})",
            f"🚪 *Oda Sayısı:* *{room}*",
            m2_text,
            "",
            f"📌 *Başlık:* {title}",
            id_text,
            f"🌐 *Kaynak:* {source}",
            "",
            "🔗 *İNDİRİMLİ İLAN LİNKİ:*",
            f"{clean_url}"
        ]
        return "\n".join(lines)





    async def send_event_notification(self, event: Dict[str, Any]) -> bool:
        """Bildirimi WhatsApp API üzerinden iletir (Fotoğraflı veya Metin)."""
        if not self.is_configured():
            return False

        event_type = event.get("type")
        item = event.get("listing", {})

        if event_type == "NEW":
            message = self.format_new_listing_message(item)
        elif event_type == "PRICE_DROP":
            message = self.format_price_drop_message(event)
        else:
            return False

        image_url = item.get("image_url", "")

        # 1. UltraMsg Servisi
        if self.provider == "ultramsg":
            return await self._send_ultramsg(message, image_url)
        # 2. Green-API Servisi
        elif self.provider == "greenapi":
            return await self._send_greenapi(message, image_url)
        else:
            return await self._send_ultramsg(message, image_url)

    async def _send_ultramsg(self, message: str, image_url: str) -> bool:
        """UltraMsg API entegrasyonu"""
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                if image_url and image_url.startswith("http"):
                    api_url = f"https://api.ultramsg.com/{self.instance_id}/messages/image"
                    payload = {
                        "token": self.token,
                        "to": self.target,
                        "image": image_url,
                        "caption": message
                    }
                else:
                    api_url = f"https://api.ultramsg.com/{self.instance_id}/messages/chat"
                    payload = {
                        "token": self.token,
                        "to": self.target,
                        "body": message
                    }

                resp = await client.post(api_url, data=payload)
                if resp.status_code == 200:
                    logger.info(f"✅ WhatsApp (UltraMsg) bildirimi gönderildi -> {self.target}")
                    return True
                else:
                    logger.warning(f"WhatsApp UltraMsg API Yanıtı ({resp.status_code}): {resp.text}")
                    if image_url:
                        fallback_url = f"https://api.ultramsg.com/{self.instance_id}/messages/chat"
                        fb_resp = await client.post(fallback_url, data={"token": self.token, "to": self.target, "body": message})
                        return fb_resp.status_code == 200
        except Exception as e:
            logger.error(f"WhatsApp UltraMsg gönderim hatası: {e}")
        return False

    async def _send_greenapi(self, message: str, image_url: str) -> bool:
        """Green-API entegrasyonu"""
        try:
            host = "https://api.green-api.com"
            async with httpx.AsyncClient(timeout=20) as client:
                chat_id = self.target if "@" in self.target else f"{self.target}@c.us"
                
                if image_url and image_url.startswith("http"):
                    api_url = f"{host}/waInstance{self.instance_id}/sendFileByUrl/{self.token}"
                    payload = {
                        "chatId": chat_id,
                        "urlFile": image_url,
                        "fileName": "daire.jpg",
                        "caption": message
                    }
                else:
                    api_url = f"{host}/waInstance{self.instance_id}/sendMessage/{self.token}"
                    payload = {
                        "chatId": chat_id,
                        "message": message
                    }

                resp = await client.post(api_url, json=payload)
                if resp.status_code == 200:
                    logger.info(f"✅ WhatsApp (Green-API) bildirimi gönderildi -> {self.target}")
                    return True
                else:
                    logger.warning(f"WhatsApp Green-API Yanıtı ({resp.status_code}): {resp.text}")
        except Exception as e:
            logger.error(f"WhatsApp Green-API gönderim hatası: {e}")
        return False

whatsapp_notifier = WhatsAppNotifier()
