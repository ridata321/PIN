# 小機票

機票追蹤機器人。盯住一段**出發日區間裡的每一天**，記錄票價，然後在一個網頁看板上告訴你哪一天飛最便宜、那天有哪些班次可以選。

目前追蹤：

| 代號 | 航線 | 出發日區間 | 天數 | 停留 |
|---|---|---|---|---|
| `DPS-MEL` | 峇里島 ⇄ 墨爾本（來回） | 2026-09-24 → 2027-02-01 | 131 | 14 天 |
| `SUB-TPE` | 泗水 ⇄ 台灣桃園（來回・直達或轉機） | 2026-09-24 → 2027-06-30 | 280 | 14 天 |
| `SUB-KUL` | 泗水 ⇄ 吉隆坡（來回） | 2026-09-24 → 2027-02-01 | 131 | 7 天 |
| `SUB-SIN` | 泗水 ⇄ 新加坡樟宜（來回） | 2026-09-24 → 2027-02-01 | 131 | 7 天 |

合計 **673 個「航線 × 出發日」**。

票價以**印尼盾（IDR）**抓取並儲存；看板右上角可切換成台幣、新幣、馬幣、美金。

---

## 三件你一定要先改的事

**停留天數。** `stay_days` 全都是我先填的（長程 14 天、短程 7 天）。來回票一定要有回程日，程式用「出發日 + stay_days」推算。實際行程不同就改 `config/watches.csv` 的 `stay_days`。

**吉隆坡和樟宜的日期區間。** 你只說過要追這兩條，沒給日期，我先填 2026-09-24 → 2027-02-01。不對就改 `date_from` / `date_to`。

**目標價。** `target_price` 我留空了。填了之後低於它的日子會在看板上標出來。

## 五分鐘上線

1. **開一個 GitHub repo**，把這整個資料夾推上去。
2. **Settings → Actions → General → Workflow permissions**，選 **Read and write permissions**。
   （程式要把抓到的價格 commit 回 repo，沒開會推不上去。）
3. **Settings → Pages**，Source 選 `Deploy from a branch`，分支 `main`、資料夾 `/docs`。
   看板網址是 `https://<你的帳號>.github.io/<repo 名>/`。
4. **Actions** 分頁 → 左邊點「小機票 抓價」→ 右邊 **Run workflow** 手動跑第一次。
5. 打開看板網址。之後每 3 小時自己更新。

> GitHub 的排程在 repo 連續 60 天沒有推送後會自動停掉。這支程式每次抓價都會 commit，所以只要它在跑就不會停。

## 為什麼不是「每 3 小時把每一天都查一遍」

673 個「航線 × 出發日」，每 3 小時全查一遍是每天 5,384 次請求 —— 一定被 Google 擋，而且一輪也跑不完。

所以改成**輪流掃**：把 673 個查詢切成 8 份，每 3 小時的那一次只掃其中一份（約 84 個，跑 9 分鐘左右），一天 8 次剛好輪完一圈。**結果是每個出發日每天更新一次，而不是每 3 小時一次。**

要讓它跑更快、更不容易被擋，最有效的做法是**縮短用不到的日期區間**（例如吉隆坡、樟宜這種短程其實不用盯到明年二月）。

（反過來說，把 `scan_slices` 改小沒有用 —— 那只會讓每一輪塞更多查詢，更容易被擋。）

## 看板怎麼用

- **上排分頁**切換追蹤項目，最右邊的虛線框是「＋ 新增追蹤」。
- **摘要列**顯示這個項目的日期區間、行程、有沒有指定班次、掃描進度，右邊是整個區間最便宜的那一天。
- **「每天票價」折線圖**的 x 軸就是你的出發日區間，綠點是最低價那天。**點圖上任何一天**會展開下方面板。
- **下方面板左邊**是那天可以選的班次（時間、航空公司、轉機、飛行時間、價格）。**點一個班次 = 把它設成這個項目的指定班次**，之後就只記錄那一班的價格，而不是當天最便宜的。
- **下方面板右邊**是那一天的價格變化曲線（跑幾輪之後才會有東西）。

## 新增追蹤 / 指定班次要怎麼存回去

靜態網頁不能直接寫檔案，所以有兩條路：

**A. 接上 Apps Script（按一下就寫進試算表）**
1. 打開你的試算表 → 擴充功能 → Apps Script，把 `apps_script/Code.gs` 貼進去。
2. 部署 → 新增部署作業 → 類型「網頁應用程式」；執行身分：我；誰可以存取：任何人。
3. 把它給的網址貼到 `docs/config.js` 的 `appsScriptUrl`。

之後在看板上按「加入追蹤」或點某個班次，就會直接寫進試算表的 `watches` 分頁，下一輪抓價就照新設定跑。

**B. 不接（預設）**
看板會直接給你一列 CSV 和一個「複製」按鈕，貼到試算表 `watches` 分頁或 `config/watches.csv` 就好。

## 設定檔

`config/watches.csv` —— 要追蹤什麼

| 欄位 | 說明 |
|---|---|
| `watch_id` | 自己取的代號，歷史靠它對應，取了別改 |
| `label` | 看板上顯示的名字 |
| `from_airport` / `to_airport` | 機場三碼（泗水 SUB、峇里島 DPS、墨爾本 MEL、桃園 TPE） |
| `date_from` / `date_to` | 出發日區間。區間內每一天都會被追蹤 |
| `trip` | `round-trip` 或 `one-way` |
| `stay_days` | 來回票的停留天數，回程日 = 出發日 + 這個數字 |
| `seat` | `economy` / `premium-economy` / `business` / `first` |
| `max_stops` | 最多轉機次數。**留空 = 直達轉機都收** |
| `pin_airline` / `pin_depart_time` | 指定班次。留空 = 每天記錄最便宜的那班 |
| `target_price` | 低於它就在看板上標「到價」 |
| `enabled` | `yes` / `no`。暫時不追改 `no`，歷史保留 |

`config/fx_rates.csv` —— 看板的換算匯率，你自己填、自己更新（跟小帳的匯率分頁同一個做法）。歷史資料不會被改寫，只是乘上匯率顯示。

`config/settings.json` —— `base_currency` 是實際抓價與儲存的幣別。改了之後**新抓的**資料換幣別，舊資料保持原樣（每列都記了自己的 `currency`）。

## 同步到 Google 試算表（選用）

不設定也能跑，資料只存在 repo 的 CSV。要同步的話：

1. Google Cloud Console 開專案 → 啟用 **Google Sheets API** → 建**服務帳號** → 產生 JSON 金鑰。
2. 開一份試算表，把服務帳號信箱（`xxx@xxx.iam.gserviceaccount.com`）加為**編輯者**。
3. GitHub repo → Settings → Secrets and variables → Actions，新增：
   - `GOOGLE_SERVICE_ACCOUNT`：整份 JSON 金鑰內容
   - `SHEET_ID`：試算表網址 `/d/` 和 `/edit` 之間那段

設好之後每次抓價會往 `price_log` 分頁 append；同時若試算表有 `watches` 分頁，程式會**優先讀它**（所以看板新增的追蹤才會生效）。

## 資料來源與備案

預設用 [`fast-flights`](https://github.com/AWeirdDev/flights)（逆向 Google Flights，免費、免金鑰）。它是非官方的，Google 改版或擋 IP 時會壞 —— 看板上會出現紅色錯誤列，Actions 的 log 會寫原因。

**一個已知限制**：fast-flights 拿不到航班號，所以「指定班次」是用**航空公司 + 起飛時間**去對。同一家同一時間通常就是同一班，但航班改時刻就會對不到。要用真正的航班號就得換 SerpApi：

1. 註冊 SerpApi 拿 API key，repo Secrets 加 `SERPAPI_KEY`。
2. `.github/workflows/track.yml` 裡 `PROVIDER: google-flights` 改成 `PROVIDER: serpapi`。

其他程式都不用動 —— 抓價只透過 `src/providers.py` 的 `fetch_options()` 一個函式。

## 本機測試

```bash
pip install -r requirements.txt
python src/track.py --dry-run      # 印出這一輪要查什麼，不連外
python src/track.py --limit 3      # 只真的查 3 個，驗證來源通不通
python src/track.py                # 正常跑一輪（掃八分之一）
python src/track.py --all          # 全部查，很慢且容易被擋
python src/build_dashboard.py      # 只重畫看板資料
cd docs && python -m http.server 8000
```

## 檔案

```
config/watches.csv       追蹤什麼（你會常改）
config/fx_rates.csv      看板換算匯率（偶爾改）
config/settings.json     抓價幣別、輪掃份數、間隔秒數
src/providers.py         票價來源，換供應商只改這裡
src/track.py             主程式，Actions 每 3 小時跑
src/build_dashboard.py   整理成看板要的 data.json / detail-*.json
src/sheets.py            試算表同步（沒設定就自動略過）
data/price_log.csv       完整歷史，只新增不覆蓋
data/options.json        每個出發日最近一次的可選班次
docs/data.json           看板摘要（開頁就載入）
docs/detail-<代號>.json   各項目的價格歷史與班次（點到才載入）
docs/index.html          看板
docs/config.js           Apps Script 網址填在這
apps_script/Code.gs      讓看板能寫回試算表的那段程式
tools/seed_demo.py       產生模擬資料，讓你先看看板長什麼樣
```

## 第一次真的抓價之前

現在 repo 裡裝的是**模擬資料**（`tools/seed_demo.py` 產生的三天份假價格）。清掉：

```bash
rm data/price_log.csv data/options.json docs/data.json docs/detail-*.json
```
