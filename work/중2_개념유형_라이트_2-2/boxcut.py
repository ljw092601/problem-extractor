# -*- coding: utf-8 -*-
# 유형 쪽: gap_stop 을 크게 잡아 아래로 딸려 온 다음 '유형 n' 개념 상자(쪽 전체 폭)를 잘라 냄
# python boxcut.py <pdf> <problems.json>   (그 자리에서 고침)
import sys, json, fitz
sys.stdout.reconfigure(encoding="utf-8")
pdf, pj = sys.argv[1:3]
d = fitz.open(pdf)
data = json.load(open(pj, encoding="utf-8"))
cache, fixed = {}, 0
for p in data["problems"]:
    pno = p["pdf_page"]
    if pno not in cache:
        marks = []
        for b in d[pno].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                t = "".join(s["text"] for s in l["spans"]).strip()
                if t == "유형" and l["spans"][0]["font"].startswith("OTGongjungjeonhwa"):
                    marks.append(l["bbox"][1] - 10)
        cache[pno] = marks
    x0, y0, x1, y1 = p["bbox"]
    ys = [my for my in cache[pno] if y0 + 20 < my < y1]
    if ys:
        p["bbox"][3] = round(min(ys), 1)
        fixed += 1
        print("cut", p["page"], p["num"], round(y1), "->", p["bbox"][3])
json.dump(data, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("fixed", fixed)
