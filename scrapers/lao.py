"""
lao.py — Scraper สำหรับหวยลาว
แหล่งข้อมูล: laohuay.com, lottovip.com (public HTML feeds)
ออกทุก จ-ศ เวลา 18:20 น.
"""
import httpx
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
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
}


# ─── Source 1: laohuay.com ───────────────────────────────────────────────────
async def fetch_from_laohuay(client: httpx.AsyncClient) -> dict | None:
    try:
        url = "https://laohuay.com/"
        r = await client.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")

        # หาตัวเลข 4 หลัก (หวยลาวปกติ 4 ตัว)
        nums_4d = re.findall(r"\b\d{4}\b", r.text)
        nums_2d = re.findall(r"\b\d{2}\b", r.text)

        prize_4d = nums_4d[0] if nums_4d else None
        if prize_4d and len(prize_4d) == 4:
            logger.info("laohuay: 4d=%s", prize_4d)
            return {
                "source": "laohuay.com",
                "num4": prize_4d,
                "num3": prize_4d[1:],          # 3 ตัวท้าย
                "num2": prize_4d[2:],          # 2 ตัวล่าง
                "top": prize_4d,
                "bot": nums_4d[1] if len(nums_4d) > 1 else "—",
                "date": _today_th(),
                "available": True,
            }
    except Exception as e:
        logger.warning("laohuay scrape failed: %s", e)
    return None


# ─── Source 2: check-huay.com  ───────────────────────────────────────────────
async def fetch_from_checkhuay(client: httpx.AsyncClient) -> dict | None:
    try:
        url = "https://www.check-huay.com/lao"
        r = await client.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()

        nums_4d = re.findall(r"\b\d{4}\b", r.text)
        if nums_4d:
            prize = nums_4d[0]
            logger.info("check-huay lao: 4d=%s", prize)
            return {
                "source": "check-huay.com",
                "num4": prize,
                "num3": prize[1:],
                "num2": prize[2:],
                "top": prize,
                "bot": nums_4d[1] if len(nums_4d) > 1 else "—",
                "date": _today_th(),
                "available": True,
            }
    except Exception as e:
        logger.warning("check-huay lao scrape failed: %s", e)
    return None


# ─── Source 3: lottovip.com ──────────────────────────────────────────────────
async def fetch_from_lottovip(client: httpx.AsyncClient) -> dict | None:
    """ลอง lottovip aggregator"""
    try:
        url = "https://www.lottovip.com/laos/"
        r = await client.get(url, headers=HEADERS, timeout=12)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "lxml")
        num_els = soup.find_all(class_=re.compile(r"num|digit|result|prize", re.I))

        all_text = " ".join(el.get_text() for el in num_els)
        nums_4d = re.findall(r"\b\d{4}\b", all_text)

        if nums_4d:
            prize = nums_4d[0]
            return {
                "source": "lottovip.com",
                "num4": prize,
                "num3": prize[1:],
                "num2": prize[2:],
                "top": prize,
                "bot": nums_4d[1] if len(nums_4d) > 1 else "—",
                "date": _today_th(),
                "available": True,
            }
    except Exception as e:
        logger.warning("lottovip lao scrape failed: %s", e)
    return None


# ─── Main entry ───────────────────────────────────────────────────────────────
async def get_lao_result() -> dict:
    """ดึงผลหวยลาวล่าสุด ลอง 3 sources ตามลำดับ"""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        for fetcher in [fetch_from_laohuay, fetch_from_checkhuay, fetch_from_lottovip]:
            result = await fetcher(client)
            if result and result.get("num4"):
                result["fetched_at"] = datetime.now().isoformat()
                return result

    logger.error("All Lao sources failed — using fallback")
    return _fallback_lao()


# ─── Hanoi scraper ────────────────────────────────────────────────────────────
async def get_hanoi_result() -> dict:
    """ดึงผลหวยฮานอยล่าสุด"""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        try:
            url = "https://www.check-huay.com/hanoi"
            r = await client.get(url, headers=HEADERS, timeout=12)
            r.raise_for_status()

            nums_5d = re.findall(r"\b\d{5}\b", r.text)
            nums_2d = re.findall(r"\b\d{2}\b", r.text)

            if nums_5d:
                g1 = nums_5d[0]
                logger.info("hanoi: g1=%s", g1)
                return {
                    "source": "check-huay.com",
                    "g1":    g1,
                    "back3": g1[-3:],
                    "back2": g1[-2:],
                    "date":  _today_th(),
                    "available": True,
                    "fetched_at": datetime.now().isoformat(),
                }
        except Exception as e:
            logger.warning("hanoi scrape failed: %s", e)

    return _fallback_hanoi()


# ─── Fallbacks ────────────────────────────────────────────────────────────────
def _fallback_lao() -> dict:
    return {
        "source": "fallback",
        "available": False,
        "num4": "8362",
        "num3": "362",
        "num2": "62",
        "top": "8362",
        "bot": "9471",
        "date": _last_weekday_th(),
        "fetched_at": datetime.now().isoformat(),
        "note": "ไม่สามารถดึงข้อมูลจริงได้ กำลังแสดงข้อมูลสำรอง",
    }

def _fallback_hanoi() -> dict:
    return {
        "source": "fallback",
        "available": False,
        "g1": "81742",
        "back3": "742",
        "back2": "42",
        "date": _today_th(),
        "fetched_at": datetime.now().isoformat(),
        "note": "ไม่สามารถดึงข้อมูลจริงได้ กำลังแสดงข้อมูลสำรอง",
    }


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _today_th() -> str:
    d = datetime.now()
    months_th = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม",
                 "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม",
                 "พฤศจิกายน", "ธันวาคม"]
    return f"{d.day} {months_th[d.month]} {d.year + 543}"

def _last_weekday_th() -> str:
    d = datetime.now()
    # ย้อนกลับถึงวันทำการล่าสุด (จ-ศ)
    while d.weekday() > 4:
        d -= timedelta(days=1)
    months_th = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม",
                 "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม",
                 "พฤศจิกายน", "ธันวาคม"]
    return f"{d.day} {months_th[d.month]} {d.year + 543}"
