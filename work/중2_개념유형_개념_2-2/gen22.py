# -*- coding: utf-8 -*-
# 개념유형 개념 2-2: detected_labels.json(detect22.py 결과) + 손으로 확인한 번호 → layout_*.json (manual_labels)
#   번호 값: 필수 = 소단원(01, 02 …)마다 1부터, 유제 = 바로 앞 필수 번호,
#            step1 = 이어지는 step1 쪽 묶음마다 1부터, step2 = 단원마다 1부터 (OCR 로 읽힌 두 자리 번호와 맞는지 확인)
# python gen22.py <slug폴더>
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
root = sys.argv[1]
det = json.load(open(os.path.join(root, "detected_labels.json"), encoding="utf-8"))

SECTION_START = [9, 14, 19, 37, 44, 54, 67, 74, 91, 97, 101, 105, 121, 127, 139, 145, 159, 165]
UNIT_START = [7, 35, 65, 89, 119, 137, 157]

def ranges(ps):
    out = []
    for p in sorted(set(ps)):
        if out and out[-1][1] == p - 1:
            out[-1][1] = p
        else:
            out.append([p, p])
    return out

def base(pages, cols, cols_even, top_pad, gap_stop=40, body=(55, 765)):
    return {"source": "text", "pages": ranges(pages), "label_regex": "^(x{50})$", "groups": False,
            "drop_outliers": False, "body": list(body),
            "columns": [{"x": c, "label_x": [0, 1]} for c in cols],
            "columns_even": [{"x": c, "label_x": [0, 1]} for c in cols_even],
            "top_pad": top_pad, "bot_pad": 8, "gap_stop": gap_stop}

# ---- 개념 쪽: 필수 / 유제
con = sorted([x for x in det if x["kind"] in ("필수", "유제")], key=lambda x: (x["page"], x["y"]))
man, kinds, cur, sec = [], [], 0, None
for x in con:
    s = max(v for v in SECTION_START if v <= x["page"])
    if s != sec:
        sec, cur = s, 0
    if x["kind"] == "필수":
        cur += 1
    n = cur if cur else 1
    man.append({"page": x["page"], "col": 0, "y": x["y"], "num": n})
    kinds.append([x["page"], x["y"], x["kind"]])
cpages = sorted(set(x["page"] for x in con))
lay = base(cpages, [[129, 556]], [[114, 540]], 8)   # x0 = 필수 번호 알약 바로 왼쪽 (옆날개 뺌)
lay["manual_labels"] = man
json.dump(lay, open(os.path.join(root, "layout_concept.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
lay2 = dict(lay)
lay2["columns"] = [{"x": [147, 556], "label_x": [0, 1]}]
lay2["columns_even"] = [{"x": [133, 540], "label_x": [0, 1]}]
json.dump(lay2, open(os.path.join(root, "layout_yuje.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"top_pad": 8, "labels": kinds}, open(os.path.join(root, "label_kinds.json"), "w", encoding="utf-8"), ensure_ascii=False)
for p in cpages:
    print(p, " ".join(f"{k[2][0]}{m['num']}@{m['y']:.0f}" for m, k in zip(man, kinds) if m["page"] == p))

# ---- step1: 이어지는 쪽 묶음마다 1부터
s1 = sorted([x for x in det if x["kind"] == "step1" and x["y"] > 80], key=lambda x: (x["page"], x["y"]))
man1, prevp, n = [], None, 0
for x in s1:
    if prevp is None or x["page"] > prevp + 1:
        n = 0
    n += 1
    prevp = x["page"]
    if x["num"] and x["num"] != n:
        print("STEP1 번호 불일치", x["page"], x["y"], x["num"], n)
    man1.append({"page": x["page"], "col": 0, "y": x["y"], "num": n})
lay = base([x["page"] for x in s1], [[131, 556]], [[116, 540]], 8)   # x0 = 번호 바로 왼쪽 (옆날개 뺌)
lay["manual_labels"] = man1
json.dump(lay, open(os.path.join(root, "layout_step1.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 왼쪽 옆날개 빼기: 합칠 때 merge_parts.py 가 필수·step1 항목의 bbox 왼쪽을 '번호(알약) x - pad' 로 옮긴다
json.dump({"pad": 1.5,
           "concept": [[x["page"], x["y"], x["x"]] for x in con if x["kind"] == "필수"],
           "step1": [[x["page"], x["y"], x["x"]] for x in s1]},
          open(os.path.join(root, "label_x.json"), "w", encoding="utf-8"), ensure_ascii=False)

# ---- step2: 단원마다 1부터 (쪽 → 왼단 → 오른단)
s2 = sorted([x for x in det if x["kind"] == "step2"], key=lambda x: (x["page"], x["col"], x["y"]))
man2, unit, n = [], None, 0
for x in s2:
    u = max(v for v in UNIT_START if v <= x["page"])
    if u != unit:
        unit, n = u, 0
    n += 1
    if x["num"] and x["num"] != n:
        print("STEP2 번호 불일치", x["page"], x["y"], x["num"], n)
    man2.append({"page": x["page"], "col": x["col"], "y": x["y"], "num": n})
lay = base([x["page"] for x in s2], [[42, 289], [296, 556]], [[28, 275], [282, 540]], 12)
lay["manual_labels"] = man2
json.dump(lay, open(os.path.join(root, "layout_step2.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- 서술형 완성하기: 오른쪽 유제 1, 2 (예제는 풀이가 붙어 있어 뺌)
ess = {31: [118, 471], 61: [121, 464], 85: [118, 450], 115: [118, 427], 133: [116, 460], 153: [118, 450], 173: [118, 489]}
man3 = [{"page": p, "col": 0, "y": y, "num": i + 1} for p, ys in ess.items() for i, y in enumerate(ys)]
lay = base(list(ess), [[296, 552]], [[296, 552]], 14, gap_stop=130)
lay["manual_labels"] = man3
json.dump(lay, open(os.path.join(root, "layout_essay.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- 연습해 보자: 2단 1~4
pra = {32: [(0, 102, 1), (0, 441, 2), (1, 102, 3), (1, 441, 4)],
       62: [(0, 104, 1), (0, 439, 2), (1, 105, 3), (1, 439, 4)],
       86: [(0, 103, 1), (0, 457, 2), (1, 104, 3), (1, 458, 4)],
       116: [(0, 104, 1), (0, 400, 2), (1, 103, 3), (1, 400, 4)],
       134: [(0, 103, 1), (0, 432, 2), (1, 104, 3), (1, 432, 4)],
       154: [(0, 106, 1), (0, 426, 2), (1, 106, 3), (1, 426, 4)],
       174: [(0, 109, 1), (0, 428, 2), (1, 109, 3), (1, 429, 4)]}
man4 = [{"page": p, "col": c, "y": y, "num": n} for p, v in pra.items() for c, y, n in v]
lay = base(list(pra), [[42, 289], [296, 556]], [[28, 275], [282, 540]], 5)
lay["manual_labels"] = man4
json.dump(lay, open(os.path.join(root, "layout_practice.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# ---- 준비 학습 (단원 표지 다음 쪽), 아래 거꾸로 된 정답 줄은 body 로 뺌
prep = {8: [276, 486], 36: [277, 444], 66: [277, 417], 90: [274, 462], 120: [275, 433], 138: [275, 457], 158: [276, 388]}
man5 = [{"page": p, "col": 0, "y": y, "num": i + 1} for p, ys in prep.items() for i, y in enumerate(ys)]
lay = base(list(prep), [[232, 556]], [[232, 545]], 16, body=(200, 730))
lay["manual_labels"] = man5
json.dump(lay, open(os.path.join(root, "layout_prep.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("concept", len(man), "step1", len(man1), "step2", len(man2), "essay", len(man3), "practice", len(man4), "prep", len(man5))
