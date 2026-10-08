# -*- coding: utf-8 -*-
# 쌍둥이 기출 쪽: 문제 영역 아래로 딸려 온 다음 '쌍둥이 0x' 뱃지(Best of Best 왕관 포함)를 잘라 냄
# python badgecut.py <pdf> <problems.json>   (그 자리에서 고침)
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
                if t.startswith("Best of Best"):
                    marks.append((l["bbox"][0], l["bbox"][1] - 15))
                for s in l["spans"]:
                    if s["font"].startswith("ArialRounded") and 15.5 <= s["size"] <= 16.5 and s["text"].strip() == "0":
                        marks.append((s["bbox"][0] - 40, s["bbox"][1] - 8))
        cache[pno] = marks
    x0, y0, x1, y1 = p["bbox"]
    ys = [my for mx, my in cache[pno] if x0 - 5 <= mx <= x1 and y0 + 20 < my < y1]
    if ys:
        p["bbox"][3] = round(min(ys), 1)
        fixed += 1
        print("cut", p["page"], p["num"], round(y1), "->", p["bbox"][3])
json.dump(data, open(pj, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("fixed", fixed)
