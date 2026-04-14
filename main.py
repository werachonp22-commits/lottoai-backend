"""
main.py — LottoAI Pro Backend API
FastAPI server ที่ scrape ข้อมูลหวยจริงแล้ว expose เป็น REST API
พร้อม in-memory cache และ auto-refresh ทุก 15 นาที
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── scrapers ──────────────────────────────────────────────────────────────────
from scrapers.thai_gov import get_thai_gov_result
from scrapers.lao import get_lao_result, get_hanoi_result

# ── setup ─────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("lotto-api")

CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# TTL (นาที) สำหรับแต่ละหวย
CACHE_TTL = {
    "thai_gov": 60 * 6,   # 6 ชั่วโมง (หวยออกวันที่ 1 กับ 16)
    "lao":      30,        # 30 นาที
    "hanoi":    30,        # 30 นาที
}

# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="LottoAI Pro API",
    description="Lottery results scraper API สำหรับหวยรัฐบาลไทย, ลาว, และฮานอย",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # อนุญาตทุก origin (ปรับสำหรับ production)
    allow_methods=["GET"],
    allow_headers=["*"],
)


# ── Cache helpers ─────────────────────────────────────────────────────────────
def cache_path(key: str) -> Path:
    return CACHE_DIR / f"{key}.json"


def read_cache(key: str, ttl_minutes: int) -> dict | None:
    path = cache_path(key)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data.get("_cached_at", "1970-01-01"))
        if datetime.now() - cached_at < timedelta(minutes=ttl_minutes):
            logger.info("cache hit: %s (age %.1f min)", key,
                        (datetime.now() - cached_at).total_seconds() / 60)
            return data
        else:
            logger.info("cache expired: %s", key)
    except Exception as e:
        logger.warning("cache read error (%s): %s", key, e)
    return None


def write_cache(key: str, data: dict) -> None:
    data["_cached_at"] = datetime.now().isoformat()
    try:
        cache_path(key).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("cache written: %s", key)
    except Exception as e:
        logger.warning("cache write error (%s): %s", key, e)


async def get_cached_or_fetch(key: str, fetcher, ttl_minutes: int) -> dict:
    """อ่าน cache ก่อน ถ้า miss จึง scrape แล้วเขียน cache"""
    cached = read_cache(key, ttl_minutes)
    if cached:
        cached["_from_cache"] = True
        return cached

    logger.info("fetching live: %s", key)
    result = await fetcher()
    write_cache(key, result)
    result["_from_cache"] = False
    return result


# ── Endpoint helpers ──────────────────────────────────────────────────────────
def _response(data: dict) -> JSONResponse:
    data.setdefault("timestamp", datetime.now().isoformat())
    return JSONResponse(content=data)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "ok",
        "service": "LottoAI Pro API",
        "version": "1.0.0",
        "endpoints": [
            "/api/thai-gov",
            "/api/lao",
            "/api/hanoi",
            "/api/all",
            "/api/cache/clear",
            "/health",
        ],
    }


@app.get("/health", tags=["Health"])
async def health():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/thai-gov", tags=["Lottery"])
async def thai_gov():
    """ผลหวยรัฐบาลไทยล่าสุด"""
    try:
        result = await get_cached_or_fetch(
            "thai_gov", get_thai_gov_result, CACHE_TTL["thai_gov"]
        )
        return _response(result)
    except Exception as e:
        logger.error("thai-gov endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/lao", tags=["Lottery"])
async def lao():
    """ผลหวยลาวล่าสุด"""
    try:
        result = await get_cached_or_fetch(
            "lao", get_lao_result, CACHE_TTL["lao"]
        )
        return _response(result)
    except Exception as e:
        logger.error("lao endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hanoi", tags=["Lottery"])
async def hanoi():
    """ผลหวยฮานอยล่าสุด"""
    try:
        result = await get_cached_or_fetch(
            "hanoi", get_hanoi_result, CACHE_TTL["hanoi"]
        )
        return _response(result)
    except Exception as e:
        logger.error("hanoi endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/all", tags=["Lottery"])
async def all_results():
    """ดึงทุกหวยพร้อมกัน (parallel)"""
    try:
        thai, lao_res, hanoi_res = await asyncio.gather(
            get_cached_or_fetch("thai_gov", get_thai_gov_result, CACHE_TTL["thai_gov"]),
            get_cached_or_fetch("lao",      get_lao_result,      CACHE_TTL["lao"]),
            get_cached_or_fetch("hanoi",    get_hanoi_result,    CACHE_TTL["hanoi"]),
            return_exceptions=True,
        )
        return _response({
            "thai_gov": thai if isinstance(thai, dict) else {"error": str(thai)},
            "lao":      lao_res if isinstance(lao_res, dict) else {"error": str(lao_res)},
            "hanoi":    hanoi_res if isinstance(hanoi_res, dict) else {"error": str(hanoi_res)},
        })
    except Exception as e:
        logger.error("all endpoint error: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/cache/clear", tags=["Admin"])
async def clear_cache():
    """ล้าง cache ทั้งหมด (บังคับ refresh ครั้งต่อไป)"""
    cleared = []
    for f in CACHE_DIR.glob("*.json"):
        f.unlink(missing_ok=True)
        cleared.append(f.stem)
    logger.info("cache cleared: %s", cleared)
    return {"cleared": cleared, "timestamp": datetime.now().isoformat()}


@app.get("/api/cache/status", tags=["Admin"])
async def cache_status():
    """ดูสถานะ cache ปัจจุบัน"""
    status = {}
    for key, ttl in CACHE_TTL.items():
        path = cache_path(key)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                cached_at = datetime.fromisoformat(data.get("_cached_at", "1970-01-01"))
                age_min = (datetime.now() - cached_at).total_seconds() / 60
                status[key] = {
                    "cached": True,
                    "age_minutes": round(age_min, 1),
                    "ttl_minutes": ttl,
                    "expired": age_min > ttl,
                    "source": data.get("source", "unknown"),
                    "available": data.get("available", True),
                }
            except Exception:
                status[key] = {"cached": False}
        else:
            status[key] = {"cached": False}
    return status


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8765,
        reload=True,
        log_level="info",
    )
