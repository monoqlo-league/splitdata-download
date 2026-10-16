# チーム戦(event-data)の対局記録を、開催日ごとのCSVにして足す。
#
# - 大会ごとに、スケジュール(YYYYMMXX-schedule.csv)と対局記録(YYYYMMXX-gamesN.csv)を付き合わせる。
#   gamesN は、スケジュールに出てくる N番目のリーグ(1=予選 など)。
# - 開催日の対局数(その日に使う卓 × 卓ごとの試合数)だけ対局記録がそろったら、その日の分を
#   event/YYYYMMXX/YYYYMMXX-gamesN-YYYYMMDD.csv として出す。そろうまでは出さない。
# - 対局の開催日は、開始時間の日付。朝6時より前に始まった対局は前の日に数える(日付をまたいだ対局)。
#   スケジュールにない日に打たれた対局(延期など)は、その日より前で直近の開催日に数える。
# - すでに出したCSVは書き換えない。非表示状態が no でない対局は入れない。
# - その日の対局がすべて詳細成績のもと(event-data の summary/YYYYMMXX-gamesN-summary.csv)に入っていれば、出さない
#   (取得する必要がないため)。1対局でも足りなければ、その日の全対局を出す。
# - 列は対局記録と同じ(拡張機能の「対局一覧のCSVを読み込む」でそのまま読める)。
#
# 使い方: リポジトリの直下で  python3 tools/split-event.py <event-data のフォルダ>
# 終わったら node tools/build-manifest.js で files.json も作り直す(ワークフローがやる)。
import csv
import datetime
import io
import json
import os
import re
import sys
from collections import defaultdict

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "..", "event-data")
DAY_START_HOUR = 6
CELL = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})(?:\([^)]*\))?\s+(\S+)")


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    rows = [r for r in rows if any(c.strip() for c in r)]
    return (rows[0], rows[1:]) if rows else ([], [])


def schedule(path):
    """(大会名, リーグの順の一覧 [(リーグ名, {開催日(YYYYMMDD): その日の対局数})])"""
    head, rows = read_csv(path)
    col = {h.strip(): i for i, h in enumerate(head)}
    if "リーグ" not in col:
        return "", []
    title = next((r[col["大会名"]].strip() for r in rows if "大会名" in col and len(r) > col["大会名"] and r[col["大会名"]].strip()), "")
    games = [i for h, i in col.items() if re.fullmatch(r"第\d+戦", h)]
    order, slots = [], defaultdict(lambda: defaultdict(int))   # リーグ → (日, 卓) → その卓の試合数
    for r in rows:
        lg = r[col["リーグ"]].strip() if len(r) > col["リーグ"] else ""
        if not lg:
            continue
        if lg not in order:
            order.append(lg)
        count = defaultdict(int)                                  # このチームの (日, 卓) ごとの試合数
        for i in games:
            m = CELL.match(r[i] if i < len(r) else "")
            if m and "抜け番" not in r[i]:
                count[(m.group(1) + m.group(2) + m.group(3), m.group(4))] += 1
        for k, n in count.items():
            slots[lg][k] = max(slots[lg][k], n)
    out = []
    for lg in order:
        per_day = defaultdict(int)
        for (day, _table), n in slots[lg].items():
            per_day[day] += n
        out.append((lg, dict(per_day)))
    return title, out


def game_day(start):
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2})", start or "")
    if not m:
        return None
    d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if int(m.group(4)) < DAY_START_HOUR:
        d -= datetime.timedelta(days=1)
    return d.strftime("%Y%m%d")


made, waiting = [], []
for name in sorted(os.listdir(data)):
    m = re.fullmatch(r"(\d{8})-schedule\.csv", name)
    if not m:
        continue
    key = m.group(1)
    title, leagues = schedule(os.path.join(data, name))
    folder = os.path.join(root, "event", key)
    if os.path.isdir(folder) or any(os.path.exists(os.path.join(data, f"{key}-games{n}.csv")) for n in range(1, len(leagues) + 1)):
        # ページに出す大会名・リーグ名(files.json を作るときに読む)
        info = {"title": title or key, "leagues": [lg for lg, _ in leagues]}
        os.makedirs(folder, exist_ok=True)
        ip = os.path.join(folder, "info.json")
        text = json.dumps(info, ensure_ascii=False, indent=1) + "\n"
        if not os.path.exists(ip) or open(ip, encoding="utf-8").read() != text:
            with open(ip, "w", encoding="utf-8") as f:
                f.write(text)
            made.append(f"event/{key}/info.json")
    for n, (lg, per_day) in enumerate(leagues, start=1):
        src = os.path.join(data, f"{key}-games{n}.csv")
        if not os.path.exists(src) or not per_day:
            continue
        header, rows = read_csv(src)
        col = {h: i for i, h in enumerate(header)}
        if not all(c in col for c in ("開始時間", "非表示状態", "牌譜リンク")):
            print(f"::warning::{key}-games{n}.csv: 列が足りないため飛ばす")
            continue
        days = sorted(per_day)
        summed = set()
        for sp in (os.path.join(data, "summary", f"{key}-games{n}-summary.csv"), os.path.join(data, f"{key}-games{n}-summary.csv")):
            if os.path.exists(sp):
                h, rs = read_csv(sp)
                summed.update(r[0].strip() for r in rs if r)
        by_day, seen = defaultdict(list), set()
        for r in rows:
            if len(r) <= max(col.values()) or r[col["非表示状態"]].strip() != "no":
                continue
            link = r[col["牌譜リンク"]].strip()
            if not link or link in seen:
                continue
            seen.add(link)
            d = game_day(r[col["開始時間"]])
            if d is None:
                continue
            before = [x for x in days if x <= d]
            if not before:
                print(f"::warning::{key}-games{n}.csv: 最初の開催日より前の対局がある({r[col['開始時間']]})。入れない")
                continue
            by_day[before[-1]].append(r)
        for day in days:
            out = f"{key}-games{n}-{day}.csv"
            path = os.path.join(folder, out)
            if os.path.exists(path):
                continue
            got, need = len(by_day[day]), per_day[day]
            if got < need:
                if got:
                    waiting.append(f"{key} {lg} {day}: {got}/{need}対局")
                continue
            if got > need:
                print(f"::warning::{key} {lg} {day}: 対局が予定より多い({got}/{need}対局)。全部入れる")
            gid = lambda r: (re.search(r"\d{6}-[0-9a-f-]{36}", r[col["牌譜リンク"]]) or [None])[0]
            if all(gid(r) in summed for r in by_day[day]):
                continue
            chunk = sorted(by_day[day], key=lambda r: (r[col["開始時間"]], r[col["牌譜リンク"]]))
            buf = io.StringIO()
            w = csv.writer(buf, lineterminator="\n")
            w.writerow(header)
            w.writerows(chunk)
            os.makedirs(folder, exist_ok=True)
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(buf.getvalue())
            made.append(f"event/{key}/{out}")

print(f"チーム戦: 作成 {len(made)}ファイル")
for p in made:
    print("  " + p)
for w in waiting:
    print("  そろっていない: " + w)
out = os.environ.get("GITHUB_OUTPUT")
if out:
    with open(out, "a") as f:
        f.write(f"made_event={len(made)}\n")
