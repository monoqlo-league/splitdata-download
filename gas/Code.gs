// 分割CSVのダウンロード記録を、このスプレッドシートに残すためのスクリプト。
// スプレッドシートの「拡張機能」→「Apps Script」に、このファイルの中身をそのまま貼る。
// 貼ったあと「デプロイ」→「新しいデプロイ」→「ウェブアプリ」で公開する(手順は README.md)。

// 下の1行は、このスクリプトが触れる範囲を「このスプレッドシートだけ」に絞る指定。消さない。
/** @OnlyCurrentDoc */

const SHEET_NAME = 'DL記録';
const FILE_PATTERN = /^\d{6}-\d{2,3}\.csv$/;
const NAME_MAX = 30;

// ページを開いたとき: これまでの記録をすべて返す。
function doGet() {
  return json_({ ok: true, records: readRecords_() });
}

// ダウンロードボタンを押したとき: 1行追記して、最新の記録を返す。
function doPost(e) {
  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (error) {
    return json_({ ok: false, error: 'bad-request' });
  }
  const file = String((body && body.file) || '').trim();
  const name = cleanName_(body && body.name);
  if (!FILE_PATTERN.test(file) || !name) {
    return json_({ ok: false, error: 'invalid' });
  }

  // 同時に押されても行が混ざらないよう、1件ずつ処理する。
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(15000);
  } catch (error) {
    return json_({ ok: false, error: 'busy' });
  }
  try {
    const records = readRecords_();
    const mine = records.some((r) => r.file === file && r.name === name);
    const others = records.some((r) => r.file === file && r.name !== name);
    // ほかの人が取得済みのファイルは、確認(force)が付くまで記録しない。
    if (!mine && others && !body.force) {
      return json_({ ok: false, error: 'taken', records: records });
    }
    // 同じ人が同じファイルを取り直しても、行は増やさない。
    if (!mine) {
      sheet_().appendRow([new Date(), file, name]);
    }
    return json_({ ok: true, records: mine ? records : readRecords_() });
  } finally {
    lock.releaseLock();
  }
}

function cleanName_(value) {
  // 先頭の = + - @ は、シートで数式として扱われるので取り除く。
  return String(value == null ? '' : value)
    .replace(/[\u0000-\u001f\u007f]/g, ' ')
    .trim()
    .replace(/^[=+\-@\s]+/, '')
    .slice(0, NAME_MAX)
    .trim();
}

function sheet_() {
  const book = SpreadsheetApp.getActiveSpreadsheet();
  let sheet = book.getSheetByName(SHEET_NAME);
  if (!sheet) {
    sheet = book.insertSheet(SHEET_NAME);
    sheet.appendRow(['日時', 'ファイル', '名前']);
    sheet.setFrozenRows(1);
    sheet.getRange('B:C').setNumberFormat('@');
  }
  return sheet;
}

function readRecords_() {
  const values = sheet_().getDataRange().getValues();
  const records = [];
  for (let i = 1; i < values.length; i++) {
    const row = values[i];
    const file = String(row[1] == null ? '' : row[1]).trim();
    const name = String(row[2] == null ? '' : row[2]).trim();
    if (!FILE_PATTERN.test(file) || !name) continue;
    const at = row[0] instanceof Date ? row[0] : new Date(row[0]);
    records.push({ file: file, name: name, at: isNaN(at.getTime()) ? '' : at.toISOString() });
  }
  return records;
}

function json_(value) {
  return ContentService.createTextOutput(JSON.stringify(value)).setMimeType(ContentService.MimeType.JSON);
}
