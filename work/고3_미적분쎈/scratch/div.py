# -*- coding: utf-8 -*-
"""쪽별 가운데 구분선 x 측정 (100dpi, 흐린 점선도 잡게 <180 픽셀이 세로로 많이 있는 x).
    python div.py <pdf> <first> <last> <out.json> [lo hi]
결과: {쪽: [구분선 x(pt) 또는 null, 세기(행 수)]}"""
import sys, json, fitz
pdf, a, b, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
lo = int(sys.argv[5]) if len(sys.argv) > 5 else 270
hi = int(sys.argv[6]) if len(sys.argv) > 6 else 330
d = fitz.open(pdf)
res = {}
sc = 100 / 72
for pn in range(a, b + 1):
    pg = d[pn - 1]
    pix = pg.get_pixmap(dpi=100, colorspace=fitz.csGRAY, clip=fitz.Rect(0, 70, pg.rect.width, 780))
    w, h, s = pix.width, pix.height, pix.samples
    best = None
    for px in range(int(lo * sc), int(hi * sc)):
        n = 0
        for y in range(h):
            v = s[y * w + px]
            if v < 215:
                n += 1
        if best is None or n > best[1]:
            best = (px, n)
    x = round(best[0] / sc, 1)
    res[pn] = (x if best[1] > 0.35 * h else None, best[1], h)
json.dump(res, open(out, "w"))
print(" ".join(f"{p}:{v[0]}" for p, v in res.items()))

