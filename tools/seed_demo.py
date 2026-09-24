"""產生模擬資料，讓你在第一次真的抓價之前就看得到頁面長什麼樣。

    python tools/seed_demo.py

真的開始抓價之前記得清掉：
    rm data/price_log.csv data/options.json docs/data.json docs/detail-*.json
"""

from __future__ import annotations

import math
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import storage  # noqa: E402
from config import load_watches  # noqa: E402

random.seed(7)
TZ = timezone(timedelta(hours=7))
TODAY = date(2026, 9, 19)

CARRIERS = {
    "DPS-MEL": [("Jetstar", 0.86, 1), ("Qantas", 1.32, 0), ("Garuda Indonesia", 1.15, 1),
                ("Batik Air", 0.94, 1), ("Scoot", 0.90, 2), ("Singapore Airlines", 1.45, 1)],
    "SUB-TPE": [("Scoot", 0.88, 1), ("China Airlines", 1.24, 1), ("EVA Air", 1.30, 1),
                ("AirAsia", 0.82, 2), ("Cathay Pacific", 1.18, 1), ("Batik Air", 0.95, 1)],
    "SUB-KUL": [("AirAsia", 0.80, 0), ("Malaysia Airlines", 1.28, 0), ("Batik Air", 0.93, 0),
                ("Scoot", 0.99, 1), ("Citilink", 0.88, 1), ("Garuda Indonesia", 1.20, 0)],
    "SUB-SIN": [("Scoot", 0.84, 0), ("Singapore Airlines", 1.35, 0), ("Jetstar", 0.90, 0),
                ("Garuda Indonesia", 1.16, 0), ("AirAsia", 0.86, 1), ("Batik Air", 0.97, 0)],
}
BASE = {"DPS-MEL": 6_200_000, "SUB-TPE": 8_400_000,
        "SUB-KUL": 2_700_000, "SUB-SIN": 2_150_000}


def seasonal(day: date) -> float:
    f = 1.0
    if day.weekday() in (4, 6):          # 週五、週日出發貴一點
        f *= 1.07
    if day.month == 12 and day.day >= 15:  # 聖誕旺季
        f *= 1.38
    if day.month == 1 and day.day <= 5:
        f *= 1.30
    if day.month in (2, 3, 5):            # 淡季
        f *= 0.92
    f *= 1 + 0.05 * math.sin(day.toordinal() / 9)
    return f


def main() -> None:
    watches = load_watches()
    rows, store = [], {}

    for watch in watches:
        carriers = CARRIERS[watch.watch_id]
        base = BASE[watch.watch_id]
        for day in watch.depart_dates(TODAY):
            level = base * seasonal(day) * random.uniform(0.96, 1.04)

            for days_ago in (2, 1, 0):  # 三天份的每日掃描
                when = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time(), TZ)
                when += timedelta(hours=random.randint(8, 20))
                drift = level * random.uniform(0.97, 1.03)

                opts = []
                for name, mult, stops in carriers:
                    price = int(round(drift * mult * random.uniform(0.98, 1.02) / 1000) * 1000)
                    dep = f"{random.randint(0, 23):02d}:{random.choice(['05','20','35','50'])}"
                    dur = random.randint(420, 1100) + stops * 180
                    opts.append({
                        "price": price, "currency": "IDR", "airline": name,
                        "depart_time": dep,
                        "arrive_time": f"{random.randint(0, 23):02d}:{random.choice(['10','25','40','55'])}",
                        "stops": stops, "duration_min": dur, "flight_no": "",
                        "source": "google-flights",
                    })
                opts.sort(key=lambda o: o["price"])
                best = opts[0]

                rows.append({
                    "fetched_at": when.strftime("%Y-%m-%d %H:%M:%S%z"),
                    "watch_id": watch.watch_id,
                    "from_airport": watch.from_airport, "to_airport": watch.to_airport,
                    "depart": day.isoformat(),
                    "return_date": (watch.return_date(day) or "").isoformat()
                    if watch.return_date(day) else "",
                    "seat": watch.seat, "price": best["price"], "currency": "IDR",
                    "airline": best["airline"], "depart_time": best["depart_time"],
                    "arrive_time": best["arrive_time"], "stops": best["stops"],
                    "duration_min": best["duration_min"], "flight_no": "",
                    "pinned": "", "source": "google-flights", "status": "ok", "message": "",
                })
                if days_ago == 0:
                    storage.update_options(store, watch.watch_id, day.isoformat(), opts,
                                           when.strftime("%Y-%m-%d %H:%M"))

    rows.sort(key=lambda r: r["fetched_at"])
    storage.LOG.unlink(missing_ok=True)
    storage.append(rows)
    storage.save_options(store)
    print(f"模擬資料：{len(rows)} 列")

    import build_dashboard
    build_dashboard.build()


if __name__ == "__main__":
    main()
