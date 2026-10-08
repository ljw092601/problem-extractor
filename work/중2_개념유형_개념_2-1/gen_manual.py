# -*- coding: utf-8 -*-
# 개념유형 개념 2-1: 필수 문제(흰 DIN-Black 14 숫자) / 유제 N-k(초록 DIN-Bold 12 숫자) 번호를 PDF 글자에서 골라
# layout_concept_base.json + manual_labels → layout_concept.json.
# 읽을거리 쪽(○○ 속 수학)의 '기출문제는 이렇게!' Q 문제(번호 없음, Q 는 그림) → layout_reading.json (num 1)
# python gen_manual.py <pdf> <slug폴더>
import sys, json, fitz, re, os
sys.stdout.reconfigure(encoding="utf-8")
pdf, root = sys.argv[1:3]
d = fitz.open(pdf)

def pages_of(cfg):
    out = []
    for a, b in cfg["pages"]:
        out.extend(range(a, b + 1))
    return out

cfg = json.load(open(os.path.join(root, "layout_concept_base.json"), encoding="utf-8"))
man = []
for p in pages_of(cfg):
    for bl in d[p - 1].get_text("dict")["blocks"]:
        for l in bl.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if not re.fullmatch(r"\d{1,3}", t):
                    continue
                f, sz, c, x, y = s["font"], s["size"], s["color"], s["bbox"][0], s["bbox"][1]
                k = None
                if f.startswith("DIN-Black") and abs(sz - 14) < .2 and c == 0xFFFFFF and 130 <= x <= 160:
                    k = "필수"
                elif f.startswith("DIN-Bold") and abs(sz - 12) < .2 and c == 0x019E89 and 165 <= x <= 190:
                    k = "유제"
                if k:
                    man.append({"page": p, "col": 0, "y": round(y, 1), "num": int(t), "_k": k, "_x": round(x, 1)})
man.sort(key=lambda m: (m["page"], m["y"]))
# 왼쪽 옆날개 빼기: 합칠 때 merge_parts.py 가 필수·step1 항목의 bbox 왼쪽을 '번호 x - pad' 로 옮긴다 (label_x.json)
s1cfg = json.load(open(os.path.join(root, "layout_step1.json"), encoding="utf-8"))
s1 = []
for p in pages_of(s1cfg):
    for bl in d[p - 1].get_text("dict")["blocks"]:
        for l in bl.get("lines", []):
            for s in l["spans"]:
                if re.fullmatch(r"\d{1,2}", s["text"].strip()) and s["font"].startswith("Bebas") and abs(s["size"] - 17.5) < .2:
                    s1.append([p, round(s["bbox"][1], 1), round(s["bbox"][0], 1)])
json.dump({"pad": 1.5,
           "concept": [[m["page"], m["y"], m["_x"]] for m in man if m["_k"] == "필수"],
           "step1": s1}, open(os.path.join(root, "label_x.json"), "w", encoding="utf-8"), ensure_ascii=False)
for m in man:
    del m["_x"]
for p in pages_of(cfg):
    print(p, " ".join(f"{m['_k']}{m['num']}@{m['y']:.0f}" for m in man if m["page"] == p))
kinds = [[m["page"], m["y"], m["_k"]] for m in man]
json.dump(kinds, open(os.path.join(root, "label_kinds.json"), "w", encoding="utf-8"), ensure_ascii=False)
for m in man:
    del m["_k"]
# 필수 문제: 전체 폭(왼쪽 옆날개 도움말 포함). 유제: 옆날개를 빼고 ▶ 표시부터 (앞 필수 문제 옆날개 조각이 딸려 오지 않게)
# 두 레이아웃 모두 번호는 전부 넣고(영역이 다음 번호에서 끊기게), 합칠 때 merge_parts.py 가
# _concept 에서는 필수, _yuje 에서는 유제 항목만 남긴다 (label_kinds.json).
cfg["manual_labels"] = man
json.dump(cfg, open(os.path.join(root, "layout_concept.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
ycfg = dict(cfg)
ycfg["manual_labels"] = man
ycfg["columns"] = [{"x": [163, 575], "label_x": [0, 1]}]
ycfg["columns_even"] = [{"x": [152, 565], "label_x": [0, 1]}]
json.dump(ycfg, open(os.path.join(root, "layout_yuje.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("labels", len(man), "필수", sum(k[2] == "필수" for k in kinds), "유제", sum(k[2] == "유제" for k in kinds))

# 읽을거리 Q 문제
rp = [20, 46, 66, 94, 126, 142]
rman = []
for p in rp:
    best = None
    for bl in d[p - 1].get_text("dict")["blocks"]:
        for l in bl.get("lines", []):
            if 108 <= l["bbox"][0] <= 114 and l["spans"][0]["font"].startswith("YDVYGO") and l["bbox"][1] > 300:
                if best is None or l["bbox"][1] < best:
                    best = l["bbox"][1]
    print("Q", p, best)
    if best is not None:
        rman.append({"page": p, "col": 0, "y": round(best, 1), "num": 1})
rcfg = {
    "source": "text",
    "pages": [[p, p] for p in rp],
    "label_regex": "^(x{50})$",
    "groups": False,
    "drop_outliers": False,
    "body": [300, 760],
    "columns": [{"x": [80, 545], "label_x": [0, 1]}],
    "columns_even": [{"x": [80, 545], "label_x": [0, 1]}],
    "top_pad": 16,
    "bot_pad": 10,
    "gap_stop": 40,
    "manual_labels": rman,
}
json.dump(rcfg, open(os.path.join(root, "layout_reading.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("reading labels", len(rman))
