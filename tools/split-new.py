# 対局記録のCSV(monoqlo-data の YYYYMM.csv)から、まだ分割CSVに入っていない対局を
# 開始時間の古い順に10対局ずつ切り出して、YYYYMM/YYYYMM-連番.csv として足す。
#
# - すでにある分割CSVは書き換えない。入っている対局(牌譜リンクで見る)は二度と出さない。
#   同じ対局記録が何度アップロードされても、同じ対局が別のファイルに重なって入ることはない。
# - 10対局に満たない残りは出さない。次のアップロードで10対局に達したときに出す。
# - 対象は FROM_MONTH 以降の月だけ。それより前の月は手作業で分割済み。
# - 非表示状態が no でない対局は入れない。
#
# 使い方: リポジトリの直下で  python3 tools/split-new.py <monoqlo-data のフォルダ>
# 終わったら node tools/build-manifest.js で files.json も作り直す(ワークフローがやる)。
import csv
import io
import os
import re
import sys

FROM_MONTH = os.environ.get("SPLIT_FROM_MONTH", "202610")
GAMES_PER_FILE = 10

root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data = sys.argv[1] if len(sys.argv) > 1 else os.path.join(root, "..", "monoqlo-data")


def read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    rows = [r for r in rows if any(c.strip() for c in r)]
    return (rows[0], rows[1:]) if rows else ([], [])


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

    new, seen = [], set()
    for r in rows:
        if len(r) <= max(i_start, i_hide, i_link):
            continue
        link = r[i_link].strip()
        if not link or link in done or link in seen or r[i_hide].strip() != "no":
            continue
        seen.add(link)
        new.append(r)
    new.sort(key=lambda r: (r[i_start], r[i_link]))

    count = len(new) // GAMES_PER_FILE
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
    rest = len(new) - count * GAMES_PER_FILE
    print(f"{month}: 新しい対局 {len(new)} → {count}ファイル作成、{rest}対局は次回へ")

print(f"作成: {len(made)}ファイル")
for p in made:
    print("  " + p)
out = os.environ.get("GITHUB_OUTPUT")
if out:
    with open(out, "a") as f:
        f.write(f"made={len(made)}\n")
