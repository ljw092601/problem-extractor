# -*- coding: utf-8 -*-
"""extract 결과에 '단을 넘어간 묶음'의 이어진 조각(continued)을 넣고, 번호 누락 점검.
    python work/고2_쎈_미적분2/scratch/finalize.py <in problems.json> <out problems.json>
넘어간 조각: 묶음이 왼쪽 단 아래에서 시작해 오른쪽 단 위로 이어지는 쪽. 오른쪽 단 맨 위(y 50)부터
그 단 첫 문제 바로 위까지를 content_bottom 으로 잘라 앞 묶음 바로 뒤에 continued 로 넣는다."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run  # noqa  (쪽별 columns)
import fitz
from core import extract as X

PDF = "work/_src/고2/쎈/2022개정 쎈 미적분2 본책.pdf"
# (쪽, 앞 묶음 시작 번호, 조각의 첫 번호, 끝 번호)
SPILL = [(9, 9, 11, 13), (51, 291, 292, 294), (69, 427, 431, 435), (87, 557, 559, 565),
         (89, 583, 587, 589), (143, 959, 961, 964), (155, 1049, 1053, 1054), (175, 1177, 1178, 1180)]
BOT_PAD = 9

src, dst = sys.argv[1:3]
d = json.load(open(src, encoding="utf-8"))
P = d["problems"]
doc = fitz.open(PDF)
for pg, after, a, b in SPILL:
    col = run.columns_for({}, pg - 1)[1]
    tops = [p["bbox"][1] for p in P if p["page"] == pg and p["column"] == "R"]
    limit = min(tops) - 2 if tops else 790
    page = doc[pg - 1]
    gray = page.get_pixmap(dpi=X.TRIM_DPI, colorspace=fitz.csGRAY)
    bot = X.content_bottom(gray, X.TRIM_DPI / 72, col["x"][0], col["x"][1], 50, limit, 45) + BOT_PAD
    bbox = [col["x"][0], 50, col["x"][1], round(min(bot, limit), 1)]
    i = next(k for k, p in enumerate(P) if p["num"] == after and p.get("num_end") and not p.get("continued"))
    assert P[i]["num_end"] >= b, (P[i], b)
    item = {"num": a, "num_end": b, "label": f"{a:04d}~{b:04d}(이어짐)", "page": pg, "pdf_page": pg - 1,
            "column": "R", "bbox": bbox, "continued": True}
    P.insert(i + 1, item)
    print("이어짐", P[i]["label"], "->", item["label"], bbox)

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
