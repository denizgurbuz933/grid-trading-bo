# -*- coding: utf-8 -*-
"""Paper trading cüzdan, pozisyon ve emir deposu (JSON, thread-safe)."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

from .prices import margin_rate, normalize_symbol, point_value

TZ_TR = timezone(timedelta(hours=3))
_lock = threading.RLock()

DEFAULT_BALANCE = 100_000.0
STATE_VERSION = 1


def _now_iso() -> str:
    return datetime.now(TZ_TR).strftime("%Y-%m-%d %H:%M:%S")


def default_state() -> dict:
    return {
        "version": STATE_VERSION,
        "mode": "PAPER",
        "label": "Paper / Demo — gerçek para yok",
        "balance": DEFAULT_BALANCE,
        "equity": DEFAULT_BALANCE,
        "realized_pnl": 0.0,
        "positions": [],
        "orders": [],
        "closed": [],
        "logs": [
            {
                "ts": _now_iso(),
                "level": "info",
                "msg": f"Paper cüzdan açıldı · başlangıç {DEFAULT_BALANCE:,.2f} USD",
            }
        ],
        "updated_at": _now_iso(),
    }


class PaperStore:
    def __init__(self, path: str):
        self.path = path
        self._ensure()

    def _ensure(self) -> None:
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        if not os.path.exists(self.path):
            self._write(default_state())

    def _read(self) -> dict:
        with open(self.path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return default_state()
        data.setdefault("positions", [])
        data.setdefault("orders", [])
        data.setdefault("closed", [])
        data.setdefault("logs", [])
        data.setdefault("balance", DEFAULT_BALANCE)
        data.setdefault("realized_pnl", 0.0)
        return data

    def _write(self, data: dict) -> None:
        data["updated_at"] = _now_iso()
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def _log(self, data: dict, msg: str, level: str = "info") -> None:
        data["logs"].insert(0, {"ts": _now_iso(), "level": level, "msg": msg})
        data["logs"] = data["logs"][:200]

    def snapshot(self, quotes: dict[str, dict] | None = None) -> dict:
        with _lock:
            data = self._read()
            marked = self._mark_to_market(data, quotes or {})
            return marked

    def _mark_to_market(self, data: dict, quotes: dict[str, dict]) -> dict:
        unrealized = 0.0
        positions = []
        for p in data.get("positions") or []:
            sym = normalize_symbol(p["symbol"])
            q = quotes.get(sym) or {}
            price = float(q.get("price") or p.get("entry") or 0)
            entry = float(p["entry"])
            lots = float(p["lots"])
            side = p["side"]  # buy | sell
            pv = point_value(sym)
            if side == "buy":
                pnl = (price - entry) * lots * pv
            else:
                pnl = (entry - price) * lots * pv
            notional = entry * lots * pv
            pnl_pct = (pnl / notional * 100.0) if notional else 0.0
            row = dict(p)
            row["current"] = round(price, 4)
            row["pnl"] = round(pnl, 2)
            row["pnl_pct"] = round(pnl_pct, 4)
            row["display"] = "XAU/USD" if sym == "XAUUSD" else "NASDAQ"
            unrealized += pnl
            positions.append(row)
        balance = float(data.get("balance") or 0)
        out = dict(data)
        out["positions"] = positions
        out["unrealized_pnl"] = round(unrealized, 2)
        out["equity"] = round(balance + unrealized, 2)
        out["total_pnl"] = round(float(data.get("realized_pnl") or 0) + unrealized, 2)
        out["used_margin"] = round(sum(self._position_margin(p) for p in positions), 2)
        out["free_margin"] = round(out["equity"] - out["used_margin"], 2)
        return out

    @staticmethod
    def _position_margin(p: dict) -> float:
        sym = normalize_symbol(p["symbol"])
        entry = float(p["entry"])
        lots = float(p["lots"])
        return entry * lots * point_value(sym) * margin_rate(sym)

    def place_market(
        self,
        symbol: str,
        side: str,
        lots: float,
        price: float,
        order_type: str = "market",
        limit_price: float | None = None,
    ) -> dict:
        sym = normalize_symbol(symbol)
        side = (side or "").lower()
        if side not in ("buy", "sell"):
            raise ValueError("side buy veya sell olmalı")
        lots = float(lots)
        if lots <= 0:
            raise ValueError("lot > 0 olmalı")
        price = float(price)
        if price <= 0:
            raise ValueError("geçersiz fiyat")

        with _lock:
            data = self._read()
            if order_type == "limit" and limit_price:
                # Paper: limit emri bekleyen kayda al (basit)
                oid = "O-" + uuid.uuid4().hex[:8].upper()
                order = {
                    "id": oid,
                    "symbol": sym,
                    "display": "XAU/USD" if sym == "XAUUSD" else "NASDAQ",
                    "side": side,
                    "lots": lots,
                    "type": "limit",
                    "limit_price": float(limit_price),
                    "status": "pending",
                    "created_at": _now_iso(),
                }
                data["orders"].insert(0, order)
                self._log(data, f"Limit emir {oid}: {side.upper()} {lots} {sym} @ {limit_price}")
                self._write(data)
                return {"ok": True, "order": order, "state": self._mark_to_market(data, {})}

            # Market fill
            margin = price * lots * point_value(sym) * margin_rate(sym)
            marked = self._mark_to_market(data, {sym: {"price": price}})
            if marked["free_margin"] < margin * 0.5:
                # çok sıkı olmasın; yine de uyarı — paper'da düşük bakiye engeli
                if marked["equity"] < margin:
                    raise ValueError("Yetersiz paper marjin / bakiye")

            pid = "P-" + uuid.uuid4().hex[:8].upper()
            pos = {
                "id": pid,
                "symbol": sym,
                "display": "XAU/USD" if sym == "XAUUSD" else "NASDAQ",
                "side": side,
                "lots": round(lots, 4),
                "entry": round(price, 4),
                "opened_at": _now_iso(),
            }
            data["positions"].insert(0, pos)
            oid = "O-" + uuid.uuid4().hex[:8].upper()
            order = {
                "id": oid,
                "symbol": sym,
                "display": pos["display"],
                "side": side,
                "lots": round(lots, 4),
                "type": "market",
                "fill_price": round(price, 4),
                "status": "filled",
                "position_id": pid,
                "created_at": _now_iso(),
            }
            data["orders"].insert(0, order)
            yon = "Al" if side == "buy" else "Sat"
            self._log(
                data,
                f"Paper emir doldu {oid}: {yon} {lots} {pos['display']} @ {price:,.4f} (marjin ~{margin:,.2f} USD)",
            )
            self._write(data)
            return {"ok": True, "order": order, "position": pos, "state": self._mark_to_market(data, {sym: {"price": price}})}

    def close_position(self, position_id: str, price: float) -> dict:
        with _lock:
            data = self._read()
            pos = None
            keep = []
            for p in data["positions"]:
                if p["id"] == position_id:
                    pos = p
                else:
                    keep.append(p)
            if not pos:
                raise ValueError("Pozisyon bulunamadı")
            sym = normalize_symbol(pos["symbol"])
            entry = float(pos["entry"])
            lots = float(pos["lots"])
            side = pos["side"]
            price = float(price)
            pv = point_value(sym)
            if side == "buy":
                pnl = (price - entry) * lots * pv
            else:
                pnl = (entry - price) * lots * pv
            data["positions"] = keep
            data["balance"] = float(data["balance"]) + pnl
            data["realized_pnl"] = float(data.get("realized_pnl") or 0) + pnl
            closed = dict(pos)
            closed["exit"] = round(price, 4)
            closed["pnl"] = round(pnl, 2)
            closed["closed_at"] = _now_iso()
            data["closed"].insert(0, closed)
            self._log(
                data,
                f"Pozisyon kapatıldı {position_id}: P/L {pnl:+.2f} USD @ {price:,.4f}",
                "info" if pnl >= 0 else "warn",
            )
            self._write(data)
            return {"ok": True, "closed": closed, "state": self._mark_to_market(data, {sym: {"price": price}})}

    def reset(self) -> dict:
        with _lock:
            data = default_state()
            self._write(data)
            return data

    def estimate(self, symbol: str, lots: float, price: float) -> dict:
        sym = normalize_symbol(symbol)
        lots = float(lots)
        price = float(price)
        cost = price * lots * point_value(sym)
        margin = cost * margin_rate(sym)
        return {
            "symbol": sym,
            "lots": lots,
            "price": price,
            "notional": round(cost, 2),
            "margin": round(margin, 2),
            "point_value": point_value(sym),
            "margin_rate": margin_rate(sym),
        }
