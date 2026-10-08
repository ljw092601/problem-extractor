# -*- coding: utf-8 -*-
"""A(핵심유형) / B(족집게·실전) / C(개념 확인) extract 결과를 합치고 좌표 보정.
    python merge.py <pdf> <A/problems.json> <B/problems.json> <C/problems.json> <out problems.json>
보정:
  - B: 윗변 위쪽에 단 폭 절반 넘게 (20%) 칠해진 줄(제목 띠 '만점 도전 문제' 등)이 있으면 그 아래로 윗변을 내리고, 같은 단 앞 문제가 그 띠를 먹었으면 띠 위에서 자름
  - C: 개념 확인 문제 아래로 다음 개념 상자(18pt 절 번호)가 시작하면 그 위에서 자름
  - A(핵심유형 쪽)는 번호가 좌우 행 순서(1,2 / 3,4)라 쪽 안에서 번호순으로 정렬
"""
import json
import re
import sys

import fitz

pdf, fa, fb, fc, out = sys.argv[1:6]
doc = fitz.open(pdf)
load = lambda f: json.load(open(f, encoding="utf-8"))["problems"]
A, B, C = load(fa), load(fb), load(fc)

DPI = 100
sc = DPI / 72
cache = {}


def gray(pno):
    if pno not in cache:
        cache[pno] = doc[pno].get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
    return cache[pno]


def label_y(p):
    page = doc[p["pdf_page"]]
    x0, y0, x1, y1 = p["bbox"]
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if s["text"].strip() == str(p["num"]) and s["size"] > 11 and x0 <= s["bbox"][0] <= x0 + 60 \
                        and y0 - 1 <= s["bbox"][1] <= y1:
                    return s["bbox"][1]
    return None


nbar = nbot = 0
for p in B:
    ly = label_y(p)
    if ly is None:
        continue
    g = gray(p["pdf_page"])
    x0, y0, x1, _ = p["bbox"]
    px0, px1 = int(x0 * sc), int(x1 * sc)
    last = None
    for ry in range(int(y0 * sc), int((ly - 1) * sc)):
        row = g.samples[ry * g.stride + px0: ry * g.stride + px1]
        dark = sum(1 for v in row if v < 232)
        if dark > 0.2 * len(row):
            last = ry
    if last is not None:
        qx0 = px0 + int(60 * sc)                    # 띠 아래 가장자리 조각(번호 옆 도장 자리는 빼고)도 넘김
        while last + 1 < int((ly - 2) * sc) and \
                sum(1 for v in g.samples[(last + 1) * g.stride + qx0:(last + 1) * g.stride + px1] if v < 232) >= 3:
            last += 1
        p["bbox"][1] = round((last + 2) / sc, 1)
        nbar += 1
        # 띠 윗끝 → 같은 단 바로 앞 문제의 아랫변이 띠를 먹었으면 띠 위(내용 끝)에서 자름
        first = last
        lim = last - int(40 * sc)
        while first - 1 > lim and \
                sum(1 for v in g.samples[(first - 1) * g.stride + qx0:(first - 1) * g.stride + px1] if v < 232) >= 3:
            first -= 1
        band_top = first / sc
        prev = [q for q in B if q["page"] == p["page"] and q["column"] == p["column"] and q["bbox"][1] < p["bbox"][1]]
        if prev:
            q = max(prev, key=lambda q: q["bbox"][1])
            if q["bbox"][3] > band_top - 2:
                ry = first - 2
                while ry > int(q["bbox"][1] * sc) and \
                        min(g.samples[ry * g.stride + px0:ry * g.stride + px1]) >= 200:
                    ry -= 1
                q["bbox"][3] = round(min(ry / sc + 8, band_top - 2), 1)
                nbot += 1

ncut = 0
for p in C:
    page = doc[p["pdf_page"]]
    x0, y0, x1, y1 = p["bbox"]
    secs = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if re.fullmatch(r"\d", s["text"].strip()) and abs(s["size"] - 18) < 0.5 and s["bbox"][0] < 70:
                    secs.append(s["bbox"][1])
    below = [y for y in secs if y0 + 20 < y < y1 + 12]
    if below:
        p["bbox"][3] = round(min(below) - 12, 1)
        ncut += 1

core_pages = {p["page"] for p in A}
allp = A + B + C
allp.sort(key=lambda p: (p["page"], p["num"]) if p["page"] in core_pages
          else (p["page"], p["column"], p["bbox"][1]))
json.dump({"pdf": doc.name.replace("\\", "/").split("/")[-1], "problems": allp},
          open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"합침 {len(allp)} (A {len(A)}, B {len(B)}, C {len(C)}) / 띠 아래로 윗변 {nbar} / 띠 위에서 아랫변 {nbot} / 개념 상자 자름 {ncut}")
