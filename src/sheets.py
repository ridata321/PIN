"""把同一批資料同步到 Google 試算表。

需要兩個環境變數（在 GitHub 上就是 Secrets）：
  GOOGLE_SERVICE_ACCOUNT  服務帳號的 JSON 內容（整份貼進去）
  SHEET_ID                試算表網址中 /d/ 和 /edit 之間那一段

沒有設定就安靜跳過，只寫 CSV —— 所以 Google 那邊還沒弄好之前，程式照樣能跑。
"""

from __future__ import annotations

import json
import os

from storage import FIELDS

SHEET_TAB = "price_log"
WATCH_TAB = "watches"


def _client():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT")
    sheet_id = os.environ.get("SHEET_ID")
    if not raw or not sheet_id:
        return None, None

    import gspread
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_info(
        json.loads(raw),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.readonly",
        ],
    )
    return gspread.authorize(creds), sheet_id


def append(rows: list[dict]) -> str:
    """回傳一句狀態描述，方便在 log 裡看得出來有沒有同步成功。"""
    if not rows:
        return "沒有資料要同步"

    client, sheet_id = _client()
    if client is None:
        return "略過試算表同步（未設定 GOOGLE_SERVICE_ACCOUNT / SHEET_ID）"

    try:
        book = client.open_by_key(sheet_id)
        try:
            tab = book.worksheet(SHEET_TAB)
        except Exception:
            tab = book.add_worksheet(title=SHEET_TAB, rows=2000, cols=len(FIELDS))
            tab.append_row(FIELDS, value_input_option="RAW")

        if not tab.get_values("A1:A1"):
            tab.append_row(FIELDS, value_input_option="RAW")

        tab.append_rows(
            [[str(r.get(k, "")) for k in FIELDS] for r in rows],
            value_input_option="RAW",
        )
        return f"已同步 {len(rows)} 列到試算表 {SHEET_TAB}"
    except Exception as exc:  # 試算表掛掉不該讓整個抓價失敗
        return f"試算表同步失敗（CSV 已寫入，不影響資料）：{exc}"


def read_watches():
    """試算表裡有 watches 分頁就以它為準 —— 頁面上新增的追蹤項目會寫到這裡。"""
    client, sheet_id = _client()
    if client is None:
        return None
    try:
        rows = client.open_by_key(sheet_id).worksheet(WATCH_TAB).get_all_records()
    except Exception as exc:
        print(f"讀不到試算表 watches 分頁，改用 config/watches.csv：{exc}")
        return None
    if not rows:
        return None

    from config import watches_from_rows

    watches = watches_from_rows(rows)
    if watches:
        print(f"追蹤清單來源：Google 試算表 watches 分頁（{len(watches)} 個啟用）")
    return watches or None
