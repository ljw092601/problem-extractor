# -*- coding: utf-8 -*-
"""extract 결과에 '단/쪽을 넘어간 묶음'의 이어진 조각(continued)을 넣고 번호 점검.
    python finalize.py <pdf> <layout.json> <spill.json> <in problems.json> <out problems.json>
spill.json: [[쪽, 앞 묶음 시작 번호, 조각 첫 번호, 조각 끝 번호, 단(기본 "R")], ...]
조각 영역 = 그 단 맨 위(body[0]) ~ 그 단 첫 문제 바로 위 (내용 바닥까지)."""
import json, os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run  # noqa  쪽별 columns (geom.json/div.json)
import fitz
from core import extract as X

pdf, lay, spill, src, dst = sys.argv[1:6]
cfg = json.load(open(lay, encoding="utf-8"))
SPILL = json.load(open(spill, encoding="utf-8"))
d = json.load(open(src, encoding="utf-8"))
P = d["problems"]
doc = fitz.open(pdf)
top0 = cfg["body"][0]
for sp in SPILL:
    pg, after, a, b = sp[:4]
    cname = sp[4] if len(sp) > 4 else "R"
    col = X.columns_for(cfg, pg - 1)["LR".index(cname)]
    tops = [p["bbox"][1] for p in P if p["page"] == pg and p["column"] == cname]
    limit = min(tops) - 2 if tops else cfg["body"][1]
    gray = doc[pg - 1].get_pixmap(dpi=X.TRIM_DPI, colorspace=fitz.csGRAY)
    bot = X.content_bottom(gray, X.TRIM_DPI / 72, col["x"][0], col["x"][1], top0, limit,
                           cfg.get("group_gap_stop", cfg["gap_stop"])) + cfg["bot_pad"]
    bbox = [col["x"][0], top0, col["x"][1], round(min(bot, limit), 1)]
    i = next(k for k, p in enumerate(P) if p["num"] == after and p.get("num_end") and not p.get("continued"))
    assert P[i]["num_end"] >= b, (P[i], b)
    w = 4 if P[i]["label"][:4].isdigit() and len(P[i]["label"].split("~")[0]) == 4 else 2
    item = {"num": a, "num_end": b, "label": f"{a:0{w}d}~{b:0{w}d}(이어짐)", "page": pg, "pdf_page": pg - 1,
            "column": cname, "bbox": bbox, "continued": True}
    P.insert(i + 1, item)
    print("이어짐", P[i]["label"], "->", item["label"], bbox)

# 문제 아래로 딸려 온 다음 제목 띠 잘라내기: bbox 아래쪽 70pt 안에 단 폭 75% 이상 가로줄(띠 윗선)이 있고
# 그 위 12~30pt 가 비어 있으면(띠 위 여백) 그 위 내용 바닥까지로 줄인다.
SC = X.TRIM_DPI / 72
_gray = {}
trimmed = []
for p in P:
    x0, y0, x1, y1 = p["bbox"]
    if y1 - y0 < 60:
        continue
    pg = p["page"]
    if pg not in _gray:
        _gray = {pg: doc[pg - 1].get_pixmap(dpi=X.TRIM_DPI, colorspace=fitz.csGRAY)}
    g = _gray[pg]
    s, st = g.samples, g.stride
    px0, px1 = int((x0 + 3) * SC), int((x1 - 3) * SC)
    need = 0.75 * (px1 - px0)

    def dark(ry):
        return sum(1 for v in s[ry * st + px0: ry * st + px1] if v < 170)

    def blank(ry):
        return min(s[ry * st + px0: ry * st + px1], default=255) >= 150

    line = None
    for ry in range(max(int((y1 - 70) * SC), int((y0 + 30) * SC)), int(y1 * SC)):
        if dark(ry) >= need:
            line = ry
            break
    if line is None:
        continue
    if not all(blank(ry) for ry in range(line - int(30 * SC), line - int(12 * SC))):
        continue
    nb = X.content_bottom(g, SC, x0, x1, y0, line / SC - 14, cfg["gap_stop"]) + cfg["bot_pad"]
    nb = round(min(nb, line / SC - 10), 1)
    trimmed.append((pg, p["label"], y1, nb))
    p["bbox"][3] = nb
print("제목 띠 잘라냄", len(trimmed), trimmed)

cov = set()
for p in P:
    cov.update(range(p["num"], p.get("num_end", p["num"]) + 1))
lo, hi = min(cov), max(cov)
print("빠진 번호:", [n for n in range(lo, hi + 1) if n not in cov])
seen = {}
for p in P:
    if not p.get("continued"):
        seen[p["num"]] = seen.get(p["num"], 0) + 1
print("중복 번호:", [n for n, c in seen.items() if c > 1])
print("항목", len(P), "문제", sum(1 for p in P if not p.get("continued")),
      "묶음", sum(1 for p in P if p.get("num_end") and not p.get("continued")),
      "이어짐", sum(1 for p in P if p.get("continued")))
json.dump(d, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
