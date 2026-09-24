"""讀設定、追蹤清單與匯率表。"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "data"
DOCS = ROOT / "docs"

TRUTHY = {"yes", "y", "true", "1", "是", "開", "啟用"}


def _int(value, default=None):
    value = str(value or "").strip().replace(",", "")
    if not value:
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


@dataclass
class Watch:
    """一個追蹤項目 = 一條航線 + 一段出發日區間。"""

    watch_id: str
    label: str
    from_airport: str
    to_airport: str
    date_from: date
    date_to: date
    trip: str           # round-trip / one-way
    stay_days: int | None
    seat: str
    max_stops: int | None
    pin_airline: str    # 指定航空公司（空 = 不指定，記錄最便宜）
    pin_depart_time: str  # 指定起飛時間 HH:MM（搭配 pin_airline 鎖定某一班）
    target_price: int | None
    note: str

    @property
    def pinned(self) -> bool:
        return bool(self.pin_airline or self.pin_depart_time)

    def depart_dates(self, today: date | None = None) -> list[date]:
        """區間內、還沒過去的每一天。"""
        today = today or date.today()
        start = max(self.date_from, today + timedelta(days=1))
        if start > self.date_to:
            return []
        return [start + timedelta(days=i) for i in range((self.date_to - start).days + 1)]

    def return_date(self, depart: date) -> date | None:
        if self.trip != "round-trip" or not self.stay_days:
            return None
        return depart + timedelta(days=self.stay_days)


def load_settings() -> dict:
    return json.loads((CONFIG / "settings.json").read_text(encoding="utf-8"))


def _watch_from_row(row: dict) -> Watch | None:
    if str(row.get("enabled", "")).strip().lower() not in TRUTHY:
        return None
    trip = (str(row.get("trip") or "round-trip")).strip()
    return Watch(
        watch_id=str(row["watch_id"]).strip(),
        label=str(row.get("label") or row["watch_id"]).strip(),
        from_airport=str(row["from_airport"]).strip().upper(),
        to_airport=str(row["to_airport"]).strip().upper(),
        date_from=datetime.strptime(str(row["date_from"]).strip(), "%Y-%m-%d").date(),
        date_to=datetime.strptime(str(row["date_to"]).strip(), "%Y-%m-%d").date(),
        trip=trip,
        stay_days=_int(row.get("stay_days"), 14 if trip == "round-trip" else None),
        seat=str(row.get("seat") or "economy").strip(),
        max_stops=_int(row.get("max_stops")),
        pin_airline=str(row.get("pin_airline") or "").strip(),
        pin_depart_time=str(row.get("pin_depart_time") or "").strip(),
        target_price=_int(row.get("target_price")),
        note=str(row.get("note") or "").strip(),
    )


def load_watches() -> list[Watch]:
    out = []
    with (CONFIG / "watches.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            watch = _watch_from_row(row)
            if watch:
                out.append(watch)
    return out


def watches_from_rows(rows: list[dict]) -> list[Watch]:
    """給 sheets.py 用：把試算表的列轉成 Watch。"""
    out = []
    for row in rows:
        try:
            watch = _watch_from_row(row)
        except (KeyError, ValueError):
            continue
        if watch:
            out.append(watch)
    return out


def load_fx() -> list[dict]:
    """per_idr = 1 印尼盾等於多少該幣別。看板的幣別切換靠這張表。"""
    out = []
    with (CONFIG / "fx_rates.csv").open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            code = (row.get("currency") or "").strip().upper()
            if code:
                out.append(
                    {
                        "code": code,
                        "per_idr": float(row["per_idr"]),
                        "label": (row.get("label") or code).strip(),
                    }
                )
    return out
