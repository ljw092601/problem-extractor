# -*- coding: utf-8 -*-
"""각 쪽·단 맨 위(50) ~ 첫 문제 top 사이에 내용이 있는 곳을 나열 (넘어간 조각 후보)."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa  (columns_for 패치 + DIV)
import fitz
from core import extract as X

pdf = "work/_src/고2/쎈/2022개정 쎈 미적분2 본책.pdf"
P = json.load(open(sys.argv[1], encoding="utf-8"))["problems"]
doc = fitz.open(pdf)
first = {}
for p in P:
    key = (p["page"], p["column"])
    if key not in first or p["bbox"][1] < first[key]:
        first[key] = p["bbox"][1]
for (pg, col), top in sorted(first.items()):
    if top < 75:
        continue
    c = run.columns_for({}, pg - 1)[0 if col == "L" else 1]
    page = doc[pg - 1]
    gray = page.get_pixmap(dpi=X.TRIM_DPI, colorspace=fitz.csGRAY)
    sc = X.TRIM_DPI / 72
    bot = X.content_bottom(gray, sc, c["x"][0], c["x"][1], 52, top - 2, 30)
    if bot > 60:
        print(pg, col, "first top", top, "content to", round(bot, 1))
