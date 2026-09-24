/**
 * 小機票 —— 讓看板可以把「新增追蹤 / 指定班次」寫進這份試算表。
 *
 * 安裝：
 *  1. 打開你的試算表 → 擴充功能 → Apps Script，把這段貼進去。
 *  2. 部署 → 新增部署作業 → 類型選「網頁應用程式」。
 *     執行身分：我；誰可以存取：任何人。
 *  3. 複製它給的網址，貼到 docs/config.js 的 appsScriptUrl。
 *
 * 只會寫 watches 分頁，不會碰 price_log。
 */

var TAB = 'watches';
var COLS = ['watch_id','label','from_airport','to_airport','date_from','date_to','trip',
            'stay_days','seat','max_stops','pin_airline','pin_depart_time','target_price',
            'enabled','note'];

function doPost(e) {
  var body = JSON.parse(e.postData.contents);
  var book = SpreadsheetApp.getActiveSpreadsheet();
  var tab = book.getSheetByName(TAB);

  if (!tab) {
    tab = book.insertSheet(TAB);
    tab.appendRow(COLS);
  }
  if (tab.getLastRow() === 0) {
    tab.appendRow(COLS);
  }

  var row = COLS.map(function (c) { return body[c] == null ? '' : String(body[c]); });
  var ids = tab.getRange(2, 1, Math.max(tab.getLastRow() - 1, 1), 1).getValues();

  for (var i = 0; i < ids.length; i++) {
    if (String(ids[i][0]).trim() === String(body.watch_id).trim()) {
      tab.getRange(i + 2, 1, 1, COLS.length).setValues([row]);   // 已存在就更新
      return ok('updated');
    }
  }
  tab.appendRow(row);                                             // 不存在就新增
  return ok('added');
}

function ok(what) {
  return ContentService
    .createTextOutput(JSON.stringify({ status: what }))
    .setMimeType(ContentService.MimeType.JSON);
}
