"""
thai_gov.py — Scraper สำหรับหวยรัฐบาลไทย
แหล่งข้อมูล: lotto.sanook.com (public HTML) + fallback ไปยัง lottery.kapook.com
"""
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "th-TH,th;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ─── Source 1: lotto.sanook.com ──────────────────────────────────────────────
async def fetch_from_sanook(client: httpx.AsyncClient) -> dict | None:
    try:
        url = "https://lotto.sanook.com/"
        r = await client.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        # ดึงรางวัลที่ 1
        prize1_el = soup.select_one(".lotto-prize-first .number, .lottery-result__prize-first span.number")
        if not prize1_el:
            prize1_el = soup.find("p", class_=re.compile(r"prize|reward|first", re.I))

        # พยายามหาตัวเลขจาก text ให้ได้ 6 หลัก
        prize1 = None
        if prize1_el:
            nums = re.findall(r"\d{6}", prize1_el.get_text())
            if nums:
                prize1 = nums[0]

        # 2 ตัวล่าง
        last2_el = soup.select_one(".lotto-prize-last2 .number, .lottery-result__last2 span.number")
        last2 = None
        if last2_el:
            nums = re.findall(r"\d{2}$", last2_el.get_text().strip())
            last2 = nums[0] if nums else re.findall(r"\d{2}", last2_el.get_text())
            if isinstance(last2, list):
                last2 = last2[0] if last2 else None

        # วันที่ออกหวย
        date_el = soup.select_one(".lotto-date, .lottery-result__date, time")
        date_str = date_el.get_text(strip=True) if date_el else ""

        # 3 ตัวหน้า / 3 ตัวหลัง
        front3 = []
        back3 = []
        try:
            # ของ sanook ส่วนใหญ่จะอยู่ใน tag ที่มี class นี้
            front_els = soup.select(".lotto-prize-front3 span.number, .lottery-result__front3 span.number")
            back_els = soup.select(".lotto-prize-back3 span.number, .lottery-result__back3 span.number")
            front3 = [re.findall(r"\d{3}", el.get_text())[0] for el in front_els if re.findall(r"\d{3}", el.get_text())][:2]
            back3 = [re.findall(r"\d{3}", el.get_text())[0] for el in back_els if re.findall(r"\d{3}", el.get_text())][:2]
        except Exception:
            pass

        # Fallback regex ถ้าหาไม่เจอ
        if not front3 or not back3:
            all_text = soup.get_text(separator=" ", strip=True).replace(",", "")
            if not front3:
                f_match = re.search(r"(?:หน้า|เลขหน้า 3 ตัว|3 ตัวหน้า).*?(?<!\d)(\d{3})(?!\d).*?(?<!\d)(\d{3})(?!\d)", all_text)
                if f_match: front3 = [f_match.group(1), f_match.group(2)]
            if not back3:
                b_match = re.search(r"(?:หลัง|เลขท้าย 3 ตัว|3 ตัวหลัง).*?(?<!\d)(\d{3})(?!\d).*?(?<!\d)(\d{3})(?!\d)", all_text)
                if b_match: back3 = [b_match.group(1), b_match.group(2)]

        if prize1:
            logger.info("sanook: prize1=%s, last2=%s", prize1, last2)
            return {
                "source": "sanook.com",
                "prize1": prize1,
                "last2": last2 or "—",
                "date": _parse_date(date_str),
                "front3": front3 if front3 else ["???", "???"],
                "back3": back3 if back3 else ["???", "???"],
            }
    except Exception as e:
        logger.warning("sanook scrape failed: %s", e)
    return None


# ─── Source 2: kapook.com ─────────────────────────────────────────────────────
async def fetch_from_kapook(client: httpx.AsyncClient) -> dict | None:
    try:
        url = "https://lottery.kapook.com/"
        r = await client.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        # หา 6-digit numbers
        all_numbers = re.findall(r"\b\d{6}\b", r.text)
        all_2d      = re.findall(r"\b\d{2}\b", r.text)

        # หา 3 ตัวหน้า / 3 ตัวหลัง จาก text โดยอิง Keyword (Strict 3 digits isolated)
        all_text = soup.get_text(separator=" ", strip=True).replace(",", "")
        front3 = []
        back3 = []
        f_match = re.search(r"(?:หน้า|เลขหน้า 3 ตัว|3 ตัวหน้า).*?(?<!\d)(\d{3})(?!\d).*?(?<!\d)(\d{3})(?!\d)", all_text)
        if f_match: front3 = [f_match.group(1), f_match.group(2)]
        b_match = re.search(r"(?:หลัง|เลขท้าย 3 ตัว|3 ตัวหลัง).*?(?<!\d)(\d{3})(?!\d).*?(?<!\d)(\d{3})(?!\d)", all_text)
        if b_match: back3 = [b_match.group(1), b_match.group(2)]

        if all_numbers:
            prize1 = all_numbers[0]
            last2  = all_2d[0] if all_2d else "—"
            logger.info("kapook: prize1=%s", prize1)
            return {
                "source": "kapook.com",
                "prize1": prize1,
                "last2": last2,
                "date": _today_th(),
                "front3": front3 if front3 else ["???", "???"],
                "back3": back3 if back3 else ["???", "???"],
            }
    except Exception as e:
        logger.warning("kapook scrape failed: %s", e)
    return None


# ─── Source 3: เสี่ยงโชค / lottery result feed ───────────────────────────────
async def fetch_from_alternate(client: httpx.AsyncClient) -> dict | None:
    """ลองเรียก JSON feed จาก alternate sources"""
    urls = [
        "https://ruay.com/lotto/result.json",
        "https://www.xn--12cg3cye0d6a3bd6c1b.com/lotto/latest.json",
    ]
    for url in urls:
        try:
            r = await client.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                prize1 = _deep_find(data, ["prize1", "first", "reward1", "number"])
                if prize1 and re.match(r"^\d{6}$", str(prize1)):
                    return {
                        "source": url,
                        "prize1": str(prize1),
                        "last2": str(_deep_find(data, ["last2", "tail2", "reward2DigitTail"]) or "—"),
                        "date": _today_th(),
                        "front3": [],
                        "back3": [],
                    }
        except Exception as e:
            logger.debug("alternate %s failed: %s", url, e)
    return None


# ─── Main entry ───────────────────────────────────────────────────────────────
async def get_thai_gov_result() -> dict:
    """ดึงผลหวยรัฐบาลไทยล่าสุด ลอง 3 sources ตามลำดับ"""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for fetcher in [fetch_from_sanook, fetch_from_kapook, fetch_from_alternate]:
            result = await fetcher(client)
            if result and result.get("prize1"):
                result["fetched_at"] = datetime.now().isoformat()
                result["available"] = True
                return result

    # Fallback — แสดงผลงวดล่าสุดที่ hard-code ไว้
    logger.error("All Thai gov sources failed — using fallback")
    return _fallback_thai_gov()


def _fallback_thai_gov() -> dict:
    return {
        "source": "fallback",
        "available": False,
        "prize1": "481625",
        "last2": "25",
        "front3": ["194", "859"],
        "back3":  ["012", "936"],
        "date": "1 เมษายน 2569",
        "fetched_at": datetime.now().isoformat(),
        "note": "ไม่สามารถดึงข้อมูลจริงได้ กำลังแสดงข้อมูลสำรอง",
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _parse_date(raw: str) -> str:
    raw = raw.strip()
    if raw:
        return raw
    return _today_th()

def _today_th() -> str:
    d = datetime.now()
    months_th = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม",
                 "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม",
                 "พฤศจิกายน", "ธันวาคม"]
    return f"{d.day} {months_th[d.month]} {d.year + 543}"

def _deep_find(obj, keys):
    """ค้นหา key ในลำดับที่กำหนดจาก dict/list ซ้อนกัน"""
    if isinstance(obj, dict):
        for k in keys:
            if k in obj:
                return obj[k]
        for v in obj.values():
            result = _deep_find(v, keys)
            if result is not None:
                return result
    elif isinstance(obj, list):
        for item in obj:
            result = _deep_find(item, keys)
            if result is not None:
                return result
    return None
