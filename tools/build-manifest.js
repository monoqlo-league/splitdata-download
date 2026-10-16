// 月ごとのフォルダにある分割CSV(個人戦)と、event/大会/ にある開催日ごとのCSV(チーム戦)を調べて、
// ページが読む一覧(files.json)を作り直す。
// 使い方: リポジトリの直下で  node tools/build-manifest.js
// CSVを足したり入れ替えたりしたら、これを実行して files.json も一緒にコミットする。
"use strict";
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const months = fs
  .readdirSync(root, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && /^\d{6}$/.test(entry.name))
  .map((entry) => entry.name)
  .sort();

function summarize(dir, name, rel) {
  const text = fs.readFileSync(path.join(dir, name), "utf8").replace(/^\uFEFF/, "");
  const lines = text.split(/\r?\n/).filter((line) => line.trim() !== "");
  const starts = lines.slice(1).map((line) => line.split(",")[0]).sort();
  return { name, path: rel, games: starts.length, from: starts[0] || "", to: starts[starts.length - 1] || "" };
}

const out = { events: [], months: [] };

// チーム戦: event/YYYYMMXX/YYYYMMXX-gamesN-YYYYMMDD.csv。大会名・リーグ名は同じフォルダの info.json
const eventRoot = path.join(root, "event");
const keys = fs.existsSync(eventRoot)
  ? fs.readdirSync(eventRoot, { withFileTypes: true }).filter((e) => e.isDirectory() && /^\d{8}$/.test(e.name)).map((e) => e.name).sort()
  : [];
for (const key of keys) {
  const dir = path.join(eventRoot, key);
  let info = {};
  try { info = JSON.parse(fs.readFileSync(path.join(dir, "info.json"), "utf8")); } catch (_) { /* 無くても出す */ }
  const leagues = Array.isArray(info.leagues) ? info.leagues : [];
  const files = fs.readdirSync(dir)
    .map((name) => ({ name, m: new RegExp(`^${key}-games(\\d+)-(\\d{8})\\.csv$`).exec(name) }))
    .filter((x) => x.m)
    .sort((a, b) => a.m[2].localeCompare(b.m[2]) || Number(a.m[1]) - Number(b.m[1]))
    .map(({ name, m }) => ({
      ...summarize(dir, name, `event/${key}/${name}`),
      league: leagues[Number(m[1]) - 1] || `${m[1]}次リーグ`,
      day: `${m[2].slice(0, 4)}-${m[2].slice(4, 6)}-${m[2].slice(6)}`,
    }));
  if (files.length) out.events.push({ key, title: info.title || key, files });
}

for (const month of months) {
  const names = fs
    .readdirSync(path.join(root, month))
    .filter((name) => new RegExp(`^${month}-\\d{2,3}\\.csv$`).test(name))
    .sort();
  const files = names.map((name) => summarize(path.join(root, month), name, `${month}/${name}`));
  if (files.length) out.months.push({ month, files });
}

fs.writeFileSync(path.join(root, "files.json"), JSON.stringify(out, null, 1) + "\n");
const total = out.months.reduce((sum, m) => sum + m.files.length, 0);
const etotal = out.events.reduce((sum, e) => sum + e.files.length, 0);
console.log(`files.json: ${out.months.length}か月, ${total}ファイル / チーム戦 ${out.events.length}大会, ${etotal}ファイル`);
