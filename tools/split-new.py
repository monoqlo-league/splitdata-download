# 対局記録のCSV(monoqlo-data の YYYYMM.csv)から、まだ分割CSVに入っていない対局を
# 開始時間の古い順に10対局ずつ切り出して、YYYYMM/YYYYMM-連番.csv として足す。
#
# - すでにある分割CSVは書き換えない。入っている対局(牌譜リンクで見る)は二度と出さない。
#   同じ対局記録が何度アップロードされても、同じ対局が別のファイルに重なって入ることはない。
# - 10対局に満たない残りは、その月のうちは出さない。次のアップロードで10対局に達したときに出す。
#   月の最終日の午前2時(日本時間)の見回り(SPLIT_FLUSH=1)で、10対局に満たない残りも1ファイルにして出す。
#   最終日のそれより後の対局は、最終日のうちは10対局ずつ出し、月が終わったら(翌月1日以降)端数も出す。
#   月が終わってから遅れて対局が上がった場合も、同じように残りを出す。
# - 対象は FROM_MONTH 以降の月だけ。それより前の月は手作業で分割済み。
# - 非表示状態が no でない対局は入れない。
# - チーム戦の対局は入れない。event-data の対局記録(*-gamesN.csv)にある対局(牌譜リンクで見る)は飛ばす。
#   event-data のフォルダは2つめの引数か、環境変数 EVENT_DATA で渡す(ワークフローが取ってくる)。
# - 月のCSVが、すでに分割した対局を MISSING_LIMIT 対局以上なくしていたら、その月は分割しない。
#   個人戦の月のCSVは、毎回その月の全対局を入れて上書きするので、ふつうは対局が減らない。
#   チーム戦の対局記録や別の月のCSVを誤って上げたときに、このきまりで止まる(monoqlo-data 側の点検が Discord に知らせる)。
#
# 使い方: リポジトリの直下で  python3 tools/split-new.py <monoqlo-data のフォルダ> [<event-data のフォルダ>]
# 終わったら node tools/build-manifest.js で files.json も作り直す(ワークフローがやる)。
import csv
import datetime
import io
import os
import re
import sys

FROM_MONTH = os.environ.get("SPLIT_FROM_MONTH", "202610")
GAMES_PER_FILE = 10
MISSING_LIMIT = 10
# 今(日本時間)。SPLIT_NOW で変えられる(確かめ用。例 2026-10-31T02:05)
JST = datetime.timezone(datetime.timedelta(hours=9))
NOW = datetime.datetime.fromisoformat(os.environ["SPLIT_NOW"]) if os.environ.get("SPLIT_NOW") else datetime.datetime.now(JST).replace(tzinfo=None)
NOW_MONTH = NOW.strftime("%Y%m")
# 最終日の午前2時の見回り: 今の月の端数も出す
LAST_DAY = (NOW + datetime.timedelta(days=1)).month != NOW.month
FLUSH_NOW = os.environ.get("SPLIT_FLUSH") == "1" and LAST_DAY and NOW.hour >= 2

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "..", "monoqlo-data")
event = sys.argv[2] if len(sys.argv) > 2 else os.environ.get("EVENT_DATA", "")


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    rows = [r for r in rows if any(c.strip() for c in r)]
    return (rows[0], rows[1:]) if rows else ([], [])


# チーム戦の対局(牌譜リンク)。event-data が無ければ空のまま(この確かめはしない)
team = set()
if event and os.path.isdir(event):
    for name in sorted(os.listdir(event)):
        if not re.fullmatch(r"\d{8}-games\d+\.csv", name):
            continue
        h, rs = read_csv(os.path.join(event, name))
        if "牌譜リンク" in h:
            k = h.index("牌譜リンク")
            team.update(r[k].strip() for r in rs if len(r) > k and r[k].strip())
    print(f"チーム戦の対局: {len(team)}対局(分割に入れない)")
else:
    print("::warning::event-data が見つからないため、チーム戦の対局を見分けられない")

made = []
for name in sorted(os.listdir(data)):
    m = re.fullmatch(r"(\d{6})\.csv", name)
    if not m or m.group(1) < FROM_MONTH:
        continue
    month = m.group(1)
    header, rows = read_csv(os.path.join(data, name))
    if not rows:
        continue
    col = {h: i for i, h in enumerate(header)}
    for need in ("開始時間", "非表示状態", "牌譜リンク"):
        if need not in col:
            sys.exit(f"{name}: 列「{need}」が無い")
    i_start, i_hide, i_link = col["開始時間"], col["非表示状態"], col["牌譜リンク"]

    folder = os.path.join(root, month)
    done, last = set(), 0
    if os.path.isdir(folder):
        for f in os.listdir(folder):
            n = re.fullmatch(month + r"-(\d{2,3})\.csv", f)
            if not n:
                continue
            last = max(last, int(n.group(1)))
            h, rs = read_csv(os.path.join(folder, f))
            if "牌譜リンク" in h:
                k = h.index("牌譜リンク")
                done.update(r[k].strip() for r in rs if len(r) > k)

    links = {r[i_link].strip() for r in rows if len(r) > i_link}
    missing = len(done - links)
    if missing >= MISSING_LIMIT:
        print(f"::warning::{name}: すでに分割した対局のうち{missing}対局が入っていない。"
              "チーム戦の対局記録や別の月のCSVが上がった可能性があるため、この月は分割しない")
        continue

    new, seen, skipped = [], set(), 0
    for r in rows:
        if len(r) <= max(i_start, i_hide, i_link):
            continue
        link = r[i_link].strip()
        if not link or link in done or link in seen or r[i_hide].strip() != "no":
            continue
        if link in team:
            skipped += 1
            continue
        seen.add(link)
        new.append(r)
    new.sort(key=lambda r: (r[i_start], r[i_link]))

    count = len(new) // GAMES_PER_FILE
    closed = month < NOW_MONTH or (month == NOW_MONTH and FLUSH_NOW)
    if closed and len(new) % GAMES_PER_FILE:
        count += 1   # 終わった月は、端数も1ファイルにする
    for j in range(count):
        chunk = new[j * GAMES_PER_FILE:(j + 1) * GAMES_PER_FILE]
        last += 1
        out = f"{month}-{last:02d}.csv"
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(header)
        w.writerows(chunk)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, out), "w", encoding="utf-8-sig", newline="") as f:
            f.write(buf.getvalue())
        made.append(f"{month}/{out}")
    rest = max(0, len(new) - count * GAMES_PER_FILE)
    if skipped:
        print(f"::warning::{name}: チーム戦の対局が{skipped}対局入っていたため、分割に入れなかった")
    print(f"{month}: 新しい対局 {len(new)} → {count}ファイル作成、{rest}対局は次回へ" + ("(月の締めなので端数も出した)" if closed and len(new) % GAMES_PER_FILE else ""))

print(f"作成: {len(made)}ファイル")
for p in made:
    print("  " + p)
out = os.environ.get("GITHUB_OUTPUT")
if out:
    with open(out, "a") as f:
        f.write(f"made={len(made)}\n")
