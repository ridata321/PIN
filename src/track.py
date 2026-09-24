"""小機票 —— 抓一輪票價。GitHub Actions 每 3 小時跑這支。

411 個「航線×出發日」沒辦法每 3 小時全部查一遍（一定被擋，也跑不完），
所以切成 scan_slices 份，每次只掃其中一份，一天 8 次剛好輪完一圈，
等於每個出發日每天更新一次。

本機測試：
    python src/track.py --dry-run          # 印出這一輪要查什麼，不連外
    python src/track.py --limit 3          # 只真的查 3 個，驗證來源通不通
    python src/track.py --all              # 不分批，全部查（很慢，會被擋）
"""

from __future__ import annotations

import argparse
import random
import time
import traceback
from datetime import datetime, timedelta, timezone

import providers
import sheets
import storage
from config import Watch, load_settings, load_watches


def parse_args():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只印出要查什麼")
    ap.add_argument("--all", action="store_true", help="不分批，全部查")
    ap.add_argument("--slice", type=int, default=None, help="指定要掃第幾份（預設由時間決定）")
    ap.add_argument("--limit", type=int, default=None, help="最多只查幾個")
    return ap.parse_args()


def build_tasks(watches: list[Watch], today) -> list[tuple[Watch, str, str | None]]:
    tasks = []
    for watch in watches:
        for day in watch.depart_dates(today):
            ret = watch.return_date(day)
            tasks.append((watch, day.isoformat(), ret.isoformat() if ret else None))
    return tasks


def main() -> int:
    args = parse_args()
    settings = load_settings()
    currency = settings["base_currency"]
    language = settings.get("language", "en-US")
    slices = max(int(settings.get("scan_slices", 8)), 1)
    keep = int(settings.get("options_per_date", 6))
    lo = float(settings.get("min_sleep_seconds", 4))
    hi = float(settings.get("max_sleep_seconds", 9))

    stamp = datetime.now(timezone(timedelta(hours=7)))
    today = stamp.date()

    watches = sheets.read_watches() or load_watches()
    if not watches:
        print("watches 裡沒有啟用的項目，結束。")
        return 0

    tasks = build_tasks(watches, today)
    total = len(tasks)

    if args.all:
        chosen, which = tasks, "全部"
    else:
        idx = args.slice if args.slice is not None else (stamp.hour // 3) % slices
        idx %= slices
        chosen = [t for i, t in enumerate(tasks) if i % slices == idx]
        which = f"第 {idx + 1}/{slices} 份"
    if args.limit:
        chosen = chosen[: args.limit]

    print(f"[{stamp:%Y-%m-%d %H:%M %Z}] 追蹤項目 {len(watches)} 個、日期共 {total} 個")
    print(f"這一輪掃 {which}，實際要查 {len(chosen)} 個，幣別 {currency}")

    if args.dry_run:
        for watch, depart, ret in chosen[:20]:
            print(f"  [dry-run] {watch.watch_id} {watch.from_airport}→{watch.to_airport} "
                  f"{depart}{' 回 ' + ret if ret else ''}")
        if len(chosen) > 20:
            print(f"  … 另外還有 {len(chosen) - 20} 個")
        return 0

    option_store = storage.load_options()
    rows: list[dict] = []
    ok = 0

    for i, (watch, depart, ret) in enumerate(chosen):
        label = f"{watch.watch_id} {depart}"
        base = {
            "fetched_at": stamp.strftime("%Y-%m-%d %H:%M:%S%z"),
            "watch_id": watch.watch_id,
            "from_airport": watch.from_airport,
            "to_airport": watch.to_airport,
            "depart": depart,
            "return_date": ret or "",
            "seat": watch.seat,
            "currency": currency,
            "pinned": "yes" if watch.pinned else "",
        }

        try:
            options = providers.fetch_options(
                from_airport=watch.from_airport,
                to_airport=watch.to_airport,
                depart=depart,
                return_date=ret,
                seat=watch.seat,
                currency=currency,
                language=language,
                max_stops=watch.max_stops,
            )
            storage.update_options(
                option_store,
                watch.watch_id,
                depart,
                [o.as_dict() for o in options[:keep]],
                stamp.strftime("%Y-%m-%d %H:%M"),
            )
            best = providers.pick(options, watch.pin_airline, watch.pin_depart_time)
            rows.append(
                {
                    **base,
                    "price": best.price,
                    "airline": best.airline,
                    "depart_time": best.depart_time,
                    "arrive_time": best.arrive_time,
                    "stops": best.stops,
                    "duration_min": best.duration_min,
                    "flight_no": best.flight_no,
                    "source": best.source,
                    "status": "ok",
                    "message": "",
                }
            )
            ok += 1
            flag = "  ★ 到價" if watch.target_price and best.price <= watch.target_price else ""
            print(f"  ✓ {label}  {best.price:,}  {best.airline} {best.depart_time} "
                  f"({best.stops} 轉){flag}")
        except Exception as exc:
            rows.append(
                {
                    **base,
                    "price": "",
                    "status": "error",
                    "message": f"{type(exc).__name__}: {exc}"[:300],
                }
            )
            print(f"  ✗ {label}  {type(exc).__name__}: {exc}")
            if i == 0:
                traceback.print_exc(limit=2)

        if i < len(chosen) - 1:
            time.sleep(random.uniform(lo, hi))

    storage.append(rows)
    storage.save_options(option_store)
    print(f"已寫入 {len(rows)} 列（成功 {ok}）到 data/price_log.csv")
    print(sheets.append(rows))

    import build_dashboard

    build_dashboard.build()

    if ok == 0:
        print("⚠ 這一輪全部失敗 —— 通常代表資料來源被擋了，看上面的錯誤訊息。")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
