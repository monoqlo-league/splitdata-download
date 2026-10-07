// 月ごとのフォルダにある分割CSVを調べて、ページが読む一覧(files.json)を作り直す。
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

const out = { months: [] };
for (const month of months) {
  const names = fs
    .readdirSync(path.join(root, month))
    .filter((name) => new RegExp(`^${month}-\\d{2,3}\\.csv$`).test(name))
    .sort();
  const files = names.map((name) => {
    const text = fs.readFileSync(path.join(root, month, name), "utf8").replace(/^﻿/, "");
    const lines = text.split(/\r?\n/).filter((line) => line.trim() !== "");
    const starts = lines.slice(1).map((line) => line.split(",")[0]).sort();
    return {
      name,
      path: `${month}/${name}`,
      games: starts.length,
      from: starts[0] || "",
      to: starts[starts.length - 1] || "",
    };
  });
  if (files.length) out.months.push({ month, files });
}

fs.writeFileSync(path.join(root, "files.json"), JSON.stringify(out, null, 1) + "\n");
const total = out.months.reduce((sum, m) => sum + m.files.length, 0);
console.log(`files.json: ${out.months.length}か月, ${total}ファイル`);
