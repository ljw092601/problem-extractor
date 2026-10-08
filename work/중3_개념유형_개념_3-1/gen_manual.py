# -*- coding: utf-8 -*-
# 개념유형 '개념편' 개념 쪽: 필수 예제(흰 GodoB 16 숫자) / 유제(노란 GodoB 10 숫자) 번호를 PDF 글자에서 골라
# manual_labels 로 만든다 (도구는 글꼴·색으로 거를 수 없어서).
# python gen_manual.py <pdf> <base_layout.json> <out_layout.json> [ex_x0 ex_x1 yu_x0 yu_x1]
import sys, json, fitz, re
sys.stdout.reconfigure(encoding="utf-8")
pdf, base, out = sys.argv[1:4]
exr = (float(sys.argv[4]), float(sys.argv[5])) if len(sys.argv) > 5 else (145, 175)
yur = (float(sys.argv[6]), float(sys.argv[7])) if len(sys.argv) > 7 else (185, 220)
cfg = json.load(open(base, encoding="utf-8"))
d = fitz.open(pdf)
pages = []
for a, b in cfg["pages"]:
    pages.extend(range(a, b + 1))
man = []
for p in pages:
    body = cfg["body"]
    for bl in d[p - 1].get_text("dict")["blocks"]:
        for l in bl.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if not re.fullmatch(r"\d{1,3}", t) or not s["font"].startswith("GodoB"):
                    continue
                x, y = s["bbox"][0], s["bbox"][1]
                if not (body[0] - 6 <= y <= body[1]):
                    continue
                kind = None
                if 15.9 <= s["size"] <= 16.1 and s["color"] == 0xFFFFFF and exr[0] <= x <= exr[1]:
                    kind = "예제"
                elif 9.9 <= s["size"] <= 10.1 and s["color"] == 0xFFF200 and yur[0] <= x <= yur[1]:
                    kind = "유제"
                if kind:
                    man.append({"page": p, "col": 0, "y": round(y, 1), "num": int(t), "_k": kind})
man.sort(key=lambda m: (m["page"], m["y"]))
for p in pages:
    ms = [f"{m['_k']}{m['num']}@{m['y']:.0f}" for m in man if m["page"] == p]
    print(p, " ".join(ms))
for m in man:
    del m["_k"]
cfg["manual_labels"] = man
json.dump(cfg, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("labels", len(man))
