# -*- coding: utf-8 -*-
"""Canlı fiyat ve mum verisi — Yahoo Finance chart API (anahtar gerekmez).

Semboller:
  XAU/USD  → Yahoo GC=F  (COMEX altın vadeli; spot'a yakın referans)
  NASDAQ   → Yahoo ^IXIC (Nasdaq Composite)
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# UI sembol → Yahoo ticker
SYMBOL_MAP = {
    "XAUUSD": "GC=F",
    "XAU/USD": "GC=F",
    "NASDAQ": "^IXIC",
    "IXIC": "^IXIC",
    "NQ": "^IXIC",
}

# Paper P/L: lot başına puan değeri (USD)
POINT_VALUE = {
    "XAUUSD": 100.0,   # 1 lot ≈ 100 oz CFD benzeri
    "NASDAQ": 1.0,     # 1 lot ≈ 1 endeks puanı
}

MARGIN_RATE = {
    "XAUUSD": 0.10,    # ~10x
    "NASDAQ": 0.05,    # ~20x
}

_cache: dict[str, tuple[float, Any]] = {}
_CACHE_TTL = 8.0  # saniye


def normalize_symbol(symbol: str) -> str:
    s = (symbol or "").strip().upper().replace(" ", "")
    if s in ("XAU/USD", "XAUUSD", "GOLD", "GC=F", "GC"):
        return "XAUUSD"
    if s in ("NASDAQ", "IXIC", "^IXIC", "NQ", "NDX"):
        return "NASDAQ"
    return s


def yahoo_ticker(symbol: str) -> str:
    key = normalize_symbol(symbol)
    return SYMBOL_MAP.get(key, SYMBOL_MAP.get(symbol, symbol))


def _http_get_json(url: str, timeout: float = 15.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _cached(key: str, fetcher):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < _CACHE_TTL:
        return hit[1]
    data = fetcher()
    _cache[key] = (now, data)
    return data


def _meta_quote(meta: dict) -> dict:
    price = float(meta.get("regularMarketPrice") or meta.get("previousClose") or 0)
    prev = float(
        meta.get("chartPreviousClose")
        or meta.get("previousClose")
        or price
    )
    day_high = float(meta.get("regularMarketDayHigh") or 0) or None
    day_low = float(meta.get("regularMarketDayLow") or 0) or None
    change = price - prev
    change_pct = (change / prev * 100.0) if prev else 0.0
    return {
        "price": round(price, 4),
        "previous_close": round(prev, 4),
        "change": round(change, 4),
        "change_pct": round(change_pct, 4),
        "day_high": round(day_high, 4) if day_high else None,
        "day_low": round(day_low, 4) if day_low else None,
        "currency": meta.get("currency") or "USD",
        "exchange": meta.get("exchangeName") or meta.get("fullExchangeName") or "",
        "yahoo_symbol": meta.get("symbol") or "",
        "instrument": meta.get("instrumentType") or "",
        "short_name": meta.get("shortName") or meta.get("longName") or "",
        "source": "yahoo_finance_chart",
    }


def fetch_quote(symbol: str) -> dict:
    """Tek sembol canlı kotasyon."""
    ui = normalize_symbol(symbol)
    ysym = yahoo_ticker(ui)

    def _do():
        q = urllib.parse.quote(ysym, safe="")
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{q}?interval=1d&range=5d"
        raw = _http_get_json(url)
        result = (raw.get("chart") or {}).get("result")
        if not result:
            err = ((raw.get("chart") or {}).get("error") or {}).get("description") or "no result"
            raise RuntimeError(f"Yahoo quote hatası ({ysym}): {err}")
        meta = result[0].get("meta") or {}
        qdata = _meta_quote(meta)
        qdata["symbol"] = ui
        qdata["display"] = "XAU/USD" if ui == "XAUUSD" else "NASDAQ"
        # Günlük high/low mumlardan doldur (meta bazen eksik)
        indicators = (result[0].get("indicators") or {}).get("quote") or []
        if indicators and (not qdata["day_high"] or not qdata["day_low"]):
            highs = [h for h in (indicators[0].get("high") or []) if h is not None]
            lows = [lo for lo in (indicators[0].get("low") or []) if lo is not None]
            if highs and not qdata["day_high"]:
                qdata["day_high"] = round(float(highs[-1]), 4)
            if lows and not qdata["day_low"]:
                qdata["day_low"] = round(float(lows[-1]), 4)
        qdata["fetched_at"] = time.time()
        return qdata

    return _cached(f"quote:{ui}", _do)


def fetch_all_quotes() -> dict[str, dict]:
    out = {}
    errors = {}
    for sym in ("XAUUSD", "NASDAQ"):
        try:
            out[sym] = fetch_quote(sym)
        except Exception as exc:  # noqa: BLE001
            errors[sym] = str(exc)
    return {"quotes": out, "errors": errors, "source": "yahoo_finance_chart"}


# UI timeframe → Yahoo interval + range
TF_MAP = {
    "1H": ("60m", "5d"),
    "4H": ("60m", "1mo"),
    "1D": ("1d", "6mo"),
    "5D": ("15m", "5d"),
    "1W": ("1d", "1y"),
    "1M": ("1wk", "2y"),
}


def fetch_candles(symbol: str, timeframe: str = "1D") -> dict:
    ui = normalize_symbol(symbol)
    ysym = yahoo_ticker(ui)
    tf = (timeframe or "1D").upper()
    interval, range_ = TF_MAP.get(tf, TF_MAP["1D"])

    def _do():
        q = urllib.parse.quote(ysym, safe="")
        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/{q}"
            f"?interval={interval}&range={range_}&includePrePost=false"
        )
        raw = _http_get_json(url)
        result = (raw.get("chart") or {}).get("result")
        if not result:
            raise RuntimeError(f"Yahoo candle hatası ({ysym})")
        ts = result[0].get("timestamp") or []
        quote = ((result[0].get("indicators") or {}).get("quote") or [{}])[0]
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        candles = []
        for i, t in enumerate(ts):
            o, h, lo, c = (
                opens[i] if i < len(opens) else None,
                highs[i] if i < len(highs) else None,
                lows[i] if i < len(lows) else None,
                closes[i] if i < len(closes) else None,
            )
            if None in (o, h, lo, c):
                continue
            candles.append(
                {
                    "time": int(t),
                    "open": round(float(o), 4),
                    "high": round(float(h), 4),
                    "low": round(float(lo), 4),
                    "close": round(float(c), 4),
                }
            )
        # 4H: 60m mumları 4'lü grupla
        if tf == "4H" and candles:
            candles = _aggregate(candles, 4)
        meta = result[0].get("meta") or {}
        return {
            "symbol": ui,
            "display": "XAU/USD" if ui == "XAUUSD" else "NASDAQ",
            "timeframe": tf,
            "interval": interval,
            "range": range_,
            "candles": candles,
            "source": "yahoo_finance_chart",
            "yahoo_symbol": ysym,
            "quote": _meta_quote(meta),
        }

    return _cached(f"candles:{ui}:{tf}", _do)


def _aggregate(candles: list[dict], n: int) -> list[dict]:
    out = []
    for i in range(0, len(candles), n):
        chunk = candles[i : i + n]
        if not chunk:
            continue
        out.append(
            {
                "time": chunk[0]["time"],
                "open": chunk[0]["open"],
                "high": max(c["high"] for c in chunk),
                "low": min(c["low"] for c in chunk),
                "close": chunk[-1]["close"],
            }
        )
    return out


def point_value(symbol: str) -> float:
    return float(POINT_VALUE.get(normalize_symbol(symbol), 1.0))


def margin_rate(symbol: str) -> float:
    return float(MARGIN_RATE.get(normalize_symbol(symbol), 0.10))
