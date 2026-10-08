# 문제 영역 아래 ~ 다음 번호(또는 본문 끝) 사이에 남은 잉크가 있는 영역 찾기 (잘림 의심)
import json, fitz, sys
S = r"C:\Users\ljw09\AppData\Local\Temp\claude\C--Users-ljw09-Desktop-promblem-area\c26382be-0e2b-44d9-be28-6fa123aea8e4\scratchpad\rpm"
d = fitz.open(S + r"\clean\22개정 RPM 미적분1 학생용 1.pdf")
v = json.load(open(S + r"\out_vec\problems.json", encoding="utf-8"))["problems"]
cfg = json.load(open(S + r"\layout_vec.json", encoding="utf-8"))
body = cfg["body"]
from collections import defaultdict
bycol = defaultdict(list)
for i, p in enumerate(v):
    bycol[(p["page"], p["column"])].append(i)
flags = []
cache = {}
for (pg, col), idx in bycol.items():
    if pg not in cache:
        cache[pg] = d[pg - 1].get_pixmap(dpi=72, colorspace=fitz.csGRAY)
    pix = cache[pg]
    for k, i in enumerate(idx):
        p = v[i]
        x0, y0, x1, y1 = p["bbox"]
        lim = v[idx[k + 1]]["bbox"][1] if k + 1 < len(idx) else body[1]
        rows = []
        for y in range(int(y1) + 1, int(lim) - 1):
            row = pix.samples[y * pix.stride + int(x0) + 2: y * pix.stride + int(x1) - 2]
            if row and min(row) < 150:
                rows.append(y)
        if rows:
            flags.append((p["page"], p["column"], p["label"], round(y1), rows[0], rows[-1], len(rows)))
for f in flags:
    print(f)
print(len(flags))
