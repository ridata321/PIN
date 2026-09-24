"""票價來源。

整個專案只透過 fetch_options() 拿資料 —— 它回傳某條航線某一天的「可選班次清單」。
要換資料來源（例如日後改用 SerpApi），只要在這裡多寫一個 provider，
改 PROVIDER 環境變數即可，其他檔案都不用動。
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass


@dataclass
class Option:
    """一個可以點選的班次。"""

    price: int
    currency: str
    airline: str
    depart_time: str   # HH:MM，去程第一段的起飛時間
    arrive_time: str
    stops: int
    duration_min: int
    flight_no: str     # fast-flights 拿不到航班號，會是空字串
    source: str

    def key(self) -> str:
        """辨識「同一班」用的鍵：航空公司 + 起飛時間。"""
        return f"{self.airline}|{self.depart_time}"

    def as_dict(self) -> dict:
        return asdict(self)


class NoResult(Exception):
    """查得到頁面但沒有可用班機（日期太遠、航線不存在、被擋等）。"""


def _hhmm(dt) -> str:
    try:
        return "%02d:%02d" % (dt.time[0], dt.time[1])
    except Exception:
        return ""


# --------------------------------------------------------------------------
# provider 1：fast-flights（逆向 Google Flights，免費、免金鑰）
# --------------------------------------------------------------------------
def _google_flights(
    from_airport, to_airport, depart, return_date, seat, currency, language, max_stops
) -> list[Option]:
    from fast_flights import FlightQuery, create_query, get_flights

    legs = [
        FlightQuery(
            date=depart, from_airport=from_airport, to_airport=to_airport, max_stops=max_stops
        )
    ]
    trip = "one-way"
    if return_date:
        legs.append(
            FlightQuery(
                date=return_date,
                from_airport=to_airport,
                to_airport=from_airport,
                max_stops=max_stops,
            )
        )
        trip = "round-trip"

    results = get_flights(
        create_query(
            flights=legs, trip=trip, seat=seat, currency=currency, language=language
        )
    )

    options: list[Option] = []
    for item in results:
        price = getattr(item, "price", None)
        if not price:
            continue
        segs = getattr(item, "flights", []) or []
        options.append(
            Option(
                price=int(price),
                currency=currency,
                airline="/".join(item.airlines) if item.airlines else "",
                depart_time=_hhmm(segs[0].departure) if segs else "",
                arrive_time=_hhmm(segs[-1].arrival) if segs else "",
                stops=max(len(segs) - 1, 0),
                duration_min=sum(int(getattr(s, "duration", 0) or 0) for s in segs),
                flight_no="",
                source="google-flights",
            )
        )

    if not options:
        raise NoResult(f"{from_airport}->{to_airport} {depart} 沒有回傳任何有價格的班機")
    return options


# --------------------------------------------------------------------------
# provider 2：SerpApi（付費；它會給航班號，鎖定特定班次更準）
# --------------------------------------------------------------------------
def _serpapi(
    from_airport, to_airport, depart, return_date, seat, currency, language, max_stops
) -> list[Option]:
    import json
    import urllib.parse
    import urllib.request

    key = os.environ.get("SERPAPI_KEY")
    if not key:
        raise RuntimeError("PROVIDER=serpapi 但沒有設定 SERPAPI_KEY")

    seat_map = {"economy": 1, "premium-economy": 2, "business": 3, "first": 4}
    params = {
        "engine": "google_flights",
        "departure_id": from_airport,
        "arrival_id": to_airport,
        "outbound_date": depart,
        "currency": currency,
        "hl": language.split("-")[0],
        "travel_class": seat_map.get(seat, 1),
        "type": 1 if return_date else 2,
        "api_key": key,
    }
    if return_date:
        params["return_date"] = return_date
    if max_stops is not None:
        params["stops"] = min(max_stops + 1, 3)

    url = "https://serpapi.com/search?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as resp:
        data = json.load(resp)

    options: list[Option] = []
    for item in (data.get("best_flights") or []) + (data.get("other_flights") or []):
        if not item.get("price"):
            continue
        segs = item.get("flights", [])
        first, last = (segs[0], segs[-1]) if segs else ({}, {})
        options.append(
            Option(
                price=int(item["price"]),
                currency=currency,
                airline="/".join(sorted({s.get("airline", "") for s in segs if s.get("airline")})),
                depart_time=(first.get("departure_airport", {}).get("time", "") or "")[-5:],
                arrive_time=(last.get("arrival_airport", {}).get("time", "") or "")[-5:],
                stops=max(len(segs) - 1, 0),
                duration_min=int(item.get("total_duration") or 0),
                flight_no=first.get("flight_number", ""),
                source="serpapi",
            )
        )

    if not options:
        raise NoResult(f"{from_airport}->{to_airport} {depart} SerpApi 沒有回傳班機")
    return options


_PROVIDERS = {"google-flights": _google_flights, "serpapi": _serpapi}


def fetch_options(
    from_airport: str,
    to_airport: str,
    depart: str,
    return_date: str | None = None,
    seat: str = "economy",
    currency: str = "IDR",
    language: str = "en-US",
    max_stops: int | None = None,
) -> list[Option]:
    """回傳該日所有可選班次，依價格由低到高排序。"""
    name = os.environ.get("PROVIDER", "google-flights")
    try:
        provider = _PROVIDERS[name]
    except KeyError:
        raise RuntimeError(f"不認得的 PROVIDER: {name}（可用：{', '.join(_PROVIDERS)}）") from None

    options = provider(
        from_airport, to_airport, depart, return_date, seat, currency, language, max_stops
    )
    return sorted(options, key=lambda o: o.price)


def pick(options: list[Option], pin_airline: str = "", pin_depart_time: str = "") -> Option:
    """沒指定就拿最便宜的；有指定就找那一班，找不到退回最便宜並由呼叫端標記。"""
    if not (pin_airline or pin_depart_time):
        return options[0]
    for opt in options:
        if pin_airline and pin_airline.lower() not in opt.airline.lower():
            continue
        if pin_depart_time and opt.depart_time != pin_depart_time:
            continue
        return opt
    raise NoResult(f"當天找不到指定的班次（{pin_airline} {pin_depart_time}）")
