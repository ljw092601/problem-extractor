"""03 여러 가지 미분법: 글자 정보에서 번호를 찾아 종류별 layout 3개를 만든다.
  layout_0.json : 배운 내용 확인하기 (3~4쪽, 1단)
  layout_A.json : 본문 '문제 N' (1단, 옆 여백 제외)
  layout_B.json : 스스로 확인하기 / 스스로 마무리하기 (2단)
python mk.py <pdf> <outdir>"""
import fitz, re, json, sys
pdf, out = sys.argv[1], sys.argv[2]
d = fitz.open(pdf)
L0, LA, LB = [], [], []
for pno in range(d.page_count):
    if pno + 1 > 60:
        break
    sp = []
    for b in d[pno].get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if re.fullmatch(r"\d{1,2}", t):
                    sp.append((t, s["bbox"], s["color"], round(s["size"], 1)))
    for t, bb, c, sz in sp:
        rec = {"page": pno + 1, "x": round(bb[0], 1), "y": round(bb[1], 1), "num": int(t)}
        if c == 3958081 and sz == 13.0:
            L0.append(rec)
        elif c == 36304 and sz == 18.0:
            LA.append(rec)
        elif c == 2781881 and sz == 17.0:
            LB.append(rec)
        elif c == 36940 and sz == 17.0:               # 마무리 01~24 (색 부분)
            pre = [u for u in sp if u[2] == 10987948 and abs(u[1][1] - bb[1]) < 1 and -2 < bb[0] - u[1][2] < 3]
            if pre:
                rec["x"] = round(pre[0][1][0], 1)
            LB.append(rec)


def col2(p, x):
    return 0 if x < 200 else 1


def pages_of(lst):
    return [[p, p] for p in sorted({r["page"] for r in lst})]


common = {"source": "text", "label_regex": "^(ZZZZ)$", "drop_outliers": False, "groups": False}
lay0 = dict(common, pages=pages_of(L0), body=[560, 712],
            columns=[{"x": [84, 560], "label_x": [88, 95]}], columns_even=[{"x": [102, 575], "label_x": [106, 113]}],
            top_pad=4, bot_pad=6, gap_stop=40,
            manual_labels=[{"page": r["page"], "col": 0, "y": r["y"], "num": r["num"]} for r in L0])
layA = dict(common, pages=pages_of(LA), body=[40, 712],
            columns=[{"x": [104, 550], "label_x": [128, 136]}], columns_even=[{"x": [127, 572], "label_x": [150, 160]}],
            top_pad=4, bot_pad=6, gap_stop=34,
            manual_labels=[{"page": r["page"], "col": 0, "y": r["y"], "num": r["num"]} for r in LA])
layB = dict(common, pages=pages_of(LB), body=[85, 712],
            columns=[{"x": [45, 283], "label_x": [49, 54]}, {"x": [294, 548], "label_x": [298, 303]}],
            columns_even=[{"x": [68, 306], "label_x": [72, 77]}, {"x": [317, 571], "label_x": [321, 326]}],
            top_pad=4, bot_pad=12, gap_stop=40,
            manual_labels=[{"page": r["page"], "col": col2(r["page"], r["x"]), "y": r["y"], "num": r["num"]} for r in LB])
for name, lay in (("0", lay0), ("A", layA), ("B", layB)):
    json.dump(lay, open(f"{out}/layout_{name}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(name, len(lay["manual_labels"]), [p[0] for p in lay["pages"]])
