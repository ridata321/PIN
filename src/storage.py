"""資料落地。

price_log.csv  每次抓到就多一列，只新增不覆蓋 —— 有歷史才畫得出走勢。
options.json   每個「追蹤項目 × 出發日」最近一次看到的可選班次清單，給頁面上的挑班次用。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from config import DATA

FIELDS = [
    "fetched_at",
    "watch_id",
    "from_airport",
    "to_airport",
    "depart",
    "return_date",
    "seat",
    "price",
    "currency",
    "airline",
    "depart_time",
    "arrive_time",
    "stops",
    "duration_min",
    "flight_no",
    "pinned",
    "source",
    "status",
    "message",
]

LOG: Path = DATA / "price_log.csv"
OPTIONS: Path = DATA / "options.json"


def append(rows: list[dict]) -> None:
    if not rows:
        return
    DATA.mkdir(parents=True, exist_ok=True)
    new_file = not LOG.exists()
    with LOG.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if new_file:
            writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDS})


def read_all() -> list[dict]:
    if not LOG.exists():
        return []
    with LOG.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def load_options() -> dict:
    if not OPTIONS.exists():
        return {}
    try:
        return json.loads(OPTIONS.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_options(store: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    OPTIONS.write_text(
        json.dumps(store, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


def update_options(store: dict, watch_id: str, depart: str, options: list[dict], when: str) -> None:
    store.setdefault(watch_id, {})[depart] = {"seen": when, "options": options}
