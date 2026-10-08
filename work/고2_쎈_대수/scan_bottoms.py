# -*- coding: utf-8 -*-
"""검수 보조: 진한 잉크(<100)만 볼 때의 아래 끝과 현재 bbox 아래 끝 차이가 큰 문제 목록 (읽기만).
python scan_bottoms.py <pdf> <problems.json> [차이 기준 pt=30]"""
import json, sys
import fitz

pdf, src = sys.argv[1:3]
lim = float(sys.argv[3]) if len(sys.argv) > 3 else 30
d = json.load(open(src, encoding="utf-8"))
doc = fitz.open(pdf)
cache = {}
out = []
for p in d["problems"]:
    x0, y0, x1, y1 = p["bbox"]
    if p["pdf_page"] not in cache:
        cache[p["pdf_page"]] = doc[p["pdf_page"]].get_pixmap(dpi=100, colorspace=fitz.csGRAY)
    pix = cache[p["pdf_page"]]
    sc = 100 / 72
    px0, px1 = int(x0 * sc), int(x1 * sc)
    last, blank, started = int(y0 * sc), 0, False
    for ry in range(int(y0 * sc), min(pix.height, int(y1 * sc))):
        row = pix.samples[ry * pix.stride + px0: ry * pix.stride + px1]
        if min(row) < 100:
            last, blank, started = ry, 0, True
        elif started:
            blank += 1
            if blank >= 30 * sc:
                break
    nb = last / sc + 12
    if y1 - nb > lim:
        out.append(p)
        print(p["page"], p["column"], p["label"], round(y0), round(y1), "->", round(nb))
print(len(out))
json.dump(out, open("scan_out.json", "w", encoding="utf-8"), ensure_ascii=False)
