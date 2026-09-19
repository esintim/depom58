import asyncio
import json
import re
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from curl_cffi.requests import AsyncSession
from loguru import logger
from config import config
from database import db

class RealEstateScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Referer": "https://www.google.com/"
        }

    def _normalize_room_count(self, raw_room: str) -> Optional[str]:
        """Oda sayısını standart formata (1+1 veya 2+1) normalize eder."""
        if not raw_room:
            return None
        text = raw_room.strip().replace(" ", "").lower()
        if "1+1" in text or "1.5+1" in text or "1oda" in text or text == "1":
            return "1+1"
        elif "2+1" in text or "2.5+1" in text or "2oda" in text or text == "2":
            return "2+1"
        elif "stüdyo" in text or "studio" in text or "1+0" in text:
            return "1+1"
        return None

    def _clean_price(self, price_val: Any) -> float:
        """Fiyat değerini temizleyip float olarak döndürür."""
        if isinstance(price_val, (int, float)):
            return float(price_val)
        if not price_val:
            return 0.0
        # "1.850.000 TL" veya "1,850,000" gibi metinleri ayıkla
        cleaned = re.sub(r"[^\d]", "", str(price_val))
        return float(cleaned) if cleaned else 0.0

    def _clean_m2(self, m2_val: Any) -> int:
        """Metrekare bilgisini integer olarak döndürür."""
        if isinstance(m2_val, int):
            return m2_val
        if not m2_val:
            return 0
        cleaned = re.sub(r"[^\d]", "", str(m2_val))
        return int(cleaned) if cleaned else 0

    async def fetch_emlakjet_listings(self, session: AsyncSession, location: Dict[str, str]) -> List[Dict[str, Any]]:
        """Emlakjet üzerinden hedef ilçe için 1+1 ve 2+1 ilanları çeker."""
        district_name = location["name"]
        url = location.get("emlakjet_url")
        if not url:
            return []

        listings = []
        try:
            resp = await session.get(url, headers=self.headers, timeout=12)
            if resp.status_code != 200:
                logger.warning(f"[Emlakjet - {district_name}] Yanıt kodu: {resp.status_code}")
                return listings

            soup = BeautifulSoup(resp.text, "lxml")
            
            # 1. JSON-LD Schema.org formatındaki ilanları tara (En güvenilir)
            for sc in soup.find_all("script", type="application/ld+json"):
                if sc.string and "RealEstateListing" in sc.string:
                    try:
                        data = json.loads(sc.string)
                        graph = data.get("@graph", [])
                        for item in graph:
                            if item.get("@type") == "RealEstateListing":
                                name = item.get("name", "")
                                link = item.get("url", "")
                                img = item.get("image", "")
                                raw_price = item.get("offers", {}).get("price", 0)
                                price = self._clean_price(raw_price)

                                props = {p.get("name"): p.get("value") for p in item.get("additionalProperty", [])}
                                raw_room = props.get("Oda Sayısı", "")
                                room = self._normalize_room_count(raw_room)
                                m2 = self._clean_m2(props.get("Metrekare", 0))
                                neighborhood = props.get("Konum", f"{district_name}")

                                # İlan ID'sini URL'den veya linkten al
                                lid_match = re.search(r"-(\d+)$", link)
                                listing_id = f"EJ-{lid_match.group(1)}" if lid_match else f"EJ-{hash(link)}"

                                # Filtre Kontrolü: 1+1 veya 2+1 ve Fiyat <= MAX_PRICE
                                if room in config.ALLOWED_ROOMS and config.MIN_PRICE <= price <= config.MAX_PRICE:
                                    listings.append({
                                        "listing_id": listing_id,
                                        "city": "Mersin",
                                        "district": district_name,
                                        "neighborhood": neighborhood,
                                        "room_count": room,
                                        "m2": m2,
                                        "price": price,
                                        "title": name,
                                        "url": link,
                                        "image_url": img,
                                        "source": "Emlakjet"
                                    })
                    except Exception as parse_err:
                        logger.debug(f"[Emlakjet] JSON-LD parse hatası: {parse_err}")

            logger.info(f"🏡 [Emlakjet - {district_name}] {len(listings)} uygun ilan (1+1 & 2+1 <= {config.MAX_PRICE:,.0f} TL) bulundu.")
            return listings

        except Exception as e:
            logger.error(f"[Emlakjet - {district_name}] İstek hatası: {e}")
            return []

    async def fetch_sahibinden_listings(self, session: AsyncSession, location: Dict[str, str]) -> List[Dict[str, Any]]:
        """Sahibinden.com üzerinden hedef ilçe için ilanları çeker."""
        district_name = location["name"]
        url = location.get("sahibinden_url")
        if not url:
            return []

        listings = []
        try:
            req_headers = dict(self.headers)
            req_headers["Host"] = "www.sahibinden.com"
            resp = await session.get(url, headers=req_headers, timeout=12)
            
            if resp.status_code == 200 and "searchResultsItem" in resp.text:
                soup = BeautifulSoup(resp.text, "lxml")
                rows = soup.select("tr.searchResultsItem")
                for row in rows:
                    try:
                        title_tag = row.select_one("a.classifiedTitle")
                        price_tag = row.select_one("td.searchResultsPriceValue")
                        loc_tag = row.select_one("td.searchResultsLocationValue")
                        attrs = row.select("td.searchResultsAttributeValue")

                        if not (title_tag and price_tag):
                            continue

                        title = title_tag.text.strip()
                        href = title_tag.get("href", "")
                        link = f"https://www.sahibinden.com{href}" if href.startswith("/") else href
                        price = self._clean_price(price_tag.text)
                        
                        room = None
                        m2 = 0
                        if len(attrs) >= 2:
                            m2 = self._clean_m2(attrs[0].text)
                            room = self._normalize_room_count(attrs[1].text)
                        
                        neighborhood = loc_tag.text.strip() if loc_tag else district_name

                        # Listing ID
                        data_id = row.get("data-id")
                        listing_id = f"SH-{data_id}" if data_id else f"SH-{hash(link)}"

                        img_tag = row.select_one("img")
                        img_url = img_tag.get("src", "") if img_tag else ""

                        if room in config.ALLOWED_ROOMS and config.MIN_PRICE <= price <= config.MAX_PRICE:
                            listings.append({
                                "listing_id": listing_id,
                                "city": "Mersin",
                                "district": district_name,
                                "neighborhood": neighborhood,
                                "room_count": room,
                                "m2": m2,
                                "price": price,
                                "title": title,
                                "url": link,
                                "image_url": img_url,
                                "source": "Sahibinden"
                            })
                    except Exception as row_err:
                        logger.debug(f"[Sahibinden] Satır parse hatası: {row_err}")

                logger.info(f"🏠 [Sahibinden - {district_name}] {len(listings)} uygun ilan bulundu.")
            else:
                logger.debug(f"[Sahibinden - {district_name}] Güvenlik kontrolü veya boş yanıt (Kod: {resp.status_code})")

            return listings
        except Exception as e:
            logger.debug(f"[Sahibinden - {district_name}] İstek atlandı: {e}")
            return []

    async def scan_for_events(self) -> List[Dict[str, Any]]:
        """
        Tüm kaynakları (Emlakjet + Sahibinden) ve ilçeleri (Erdemli + Silifke) tarar.
        Veritabanına iletir.
        YENİ İLAN ('NEW') veya FİYAT DÜŞÜŞÜ ('PRICE_DROP') olan olayları döndürür.
        """
        events = []
        async with AsyncSession(impersonate="chrome124") as session:
            for loc in config.LOCATIONS:
                district_name = loc["name"]
                
                # 1. Emlakjet Tarama
                ej_listings = await self.fetch_emlakjet_listings(session, loc)
                for item in ej_listings:
                    res = db.process_listing(item)
                    if res:
                        events.append(res)

                await asyncio.sleep(1.5)

                # 2. Sahibinden Tarama
                sh_listings = await self.fetch_sahibinden_listings(session, loc)
                for item in sh_listings:
                    res = db.process_listing(item)
                    if res:
                        events.append(res)

                await asyncio.sleep(1.5)

        logger.info(f"📊 Toplam bildirilecek olay sayısı: {len(events)} (Yeni İlan veya Fiyat Düşüşü)")
        return events
scraper = RealEstateScraper()



