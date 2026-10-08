# -*- coding: utf-8 -*-
"""각 쪽·단 맨 위(body[0]) ~ 첫 문제 top 사이에 내용이 있는 곳 나열 (넘어간 조각 후보).
    python gaps.py <pdf> <layout.json> <problems.json> [min_top]"""
import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run  # noqa  쪽별 columns (geom.json/div.json)
import fitz
from core import extract as X

pdf, lay, pj = sys.argv[1:4]
min_top = float(sys.argv[4]) if len(sys.argv) > 4 else 75
cfg = json.load(open(lay, encoding="utf-8"))
P = json.load(open(pj, encoding="utf-8"))["problems"]
doc = fitz.open(pdf)
first = {}
for p in P:
    key = (p["page"], p["column"])
    if key not in first or p["bbox"][1] < first[key]:
        first[key] = p["bbox"][1]
pages = sorted({p["page"] for p in P})
for pg in pages:
    cols = X.columns_for(cfg, pg - 1)
    for ci, name in enumerate("LR"):
        top = first.get((pg, name), cfg["body"][1])
        if top < min_top:
            continue
        c = cols[ci]
        gray = doc[pg - 1].get_pixmap(dpi=X.TRIM_DPI, colorspace=fitz.csGRAY)
        sc = X.TRIM_DPI / 72
        y0 = cfg["body"][0] + 4
        bot = X.content_bottom(gray, sc, c["x"][0] + 4, c["x"][1] - 4, y0, top - 2, 30)
        if bot > y0 + 8:
            print(pg, name, "first top", top, "content to", round(bot, 1))
