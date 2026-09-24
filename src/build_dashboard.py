"""把 price_log.csv + options.json 整理成頁面要讀的 JSON。

docs/data.json    摘要 + 每個出發日的最新票價（頁面一開啟就載入，要小）
docs/detail-<代號>.json  每個出發日的價格變化歷史 + 可點選班次（點到某一天才載入那一個）
"""

from __future__ import annotations

import json
import statistics
from datetime import datetime

import storage
from config import DOCS, load_settings, load_watches

MAX_HISTORY_POINTS = 120


def _parse_time(value: str) -> datetime | None:
    for fmt in ("%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def _verdict(price: int, others: list[int]) -> tuple[str, str]:
    if len(others) < 6:
        return "new", "資料還不夠比較"
    low, med = min(others), statistics.median(others)
    if price <= low * 1.02:
        return "cheap", "這段區間裡最便宜的那幾天"
    if price <= med:
        return "ok", "低於區間中位數"
    if price <= med * 1.2:
        return "high", "高於區間中位數"
    return "worst", "明顯偏貴"


def build() -> None:
    settings = load_settings()
    rows = storage.read_all()
    options_store = storage.load_options()
    meta = {w.watch_id: w for w in load_watches()}

    # watch_id -> depart -> 依時間排序的紀錄
    grouped: dict[str, dict[str, list[dict]]] = {}
    for row in rows:
        grouped.setdefault(row["watch_id"], {}).setdefault(row["depart"], []).append(row)

    watches_out, detail_out = [], {}

    for watch_id, by_depart in grouped.items():
        watch = meta.get(watch_id)
        by_date, history, errors, last_error = [], {}, 0, ""

        for depart in sorted(by_depart):
            entries = sorted(by_depart[depart], key=lambda r: r["fetched_at"])
            points = []
            for row in entries:
                if row.get("status") != "ok" or not row.get("price"):
                    continue
                when = _parse_time(row["fetched_at"])
                if when:
                    points.append({"t": when.isoformat(timespec="minutes"), "p": int(float(row["price"]))})

            last = entries[-1]
            if last.get("status") == "error":
                errors += 1
                last_error = last.get("message", "")

            if not points:
                continue

            newest = next(r for r in reversed(entries) if r.get("status") == "ok" and r.get("price"))
            by_date.append(
                {
                    "d": depart,
                    "r": last.get("return_date", ""),
                    "p": points[-1]["p"],
                    "a": newest.get("airline", ""),
                    "dt": newest.get("depart_time", ""),
                    "s": int(newest.get("stops") or 0),
                    "dur": int(newest.get("duration_min") or 0),
                    "n": len(points),
                }
            )
            if len(points) > 1:
                history[depart] = points[-MAX_HISTORY_POINTS:]

        if not by_date:
            continue

        prices = [d["p"] for d in by_date]
        for entry in by_date:
            entry["v"], entry["why"] = _verdict(entry["p"], prices)

        best = min(by_date, key=lambda d: d["p"])
        total_days = len(watch.depart_dates()) if watch else len(by_date)

        watches_out.append(
            {
                "id": watch_id,
                "label": watch.label if watch else watch_id,
                "from": by_date and next(iter(by_depart.values()))[0]["from_airport"],
                "to": next(iter(by_depart.values()))[0]["to_airport"],
                "date_from": watch.date_from.isoformat() if watch else by_date[0]["d"],
                "date_to": watch.date_to.isoformat() if watch else by_date[-1]["d"],
                "trip": watch.trip if watch else "",
                "stay_days": watch.stay_days if watch else None,
                "seat": watch.seat if watch else "",
                "pin_airline": watch.pin_airline if watch else "",
                "pin_depart_time": watch.pin_depart_time if watch else "",
                "target": watch.target_price if watch else None,
                "note": watch.note if watch else "",
                "scanned": len(by_date),
                "total_days": total_days,
                "errors": errors,
                "last_error": last_error,
                "low": min(prices),
                "high": max(prices),
                "median": round(statistics.median(prices)),
                "best": best,
                "by_date": by_date,
            }
        )
        detail_out[watch_id] = {
            "history": history,
            "options": options_store.get(watch_id, {}),
        }

    watches_out.sort(key=lambda w: w["id"])

    DOCS.mkdir(parents=True, exist_ok=True)
    (DOCS / "data.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "base_currency": settings["base_currency"],
                "fx": __import__("config").load_fx(),
                "watches": watches_out,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    for watch_id, payload in detail_out.items():
        (DOCS / f"detail-{watch_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )

    days = sum(w["scanned"] for w in watches_out)
    print(f"已更新看板資料：{len(watches_out)} 個追蹤項目、{days} 個出發日")


if __name__ == "__main__":
    build()
