# -*- coding: utf-8 -*-
# 개념원리 기하 (고3_개념원리_미적분 의 스크립트를 쪽 범위만 바꿔 씀): 문제 번호를 PDF 글자(글꼴·크기)로 골라 manual_labels 로 넣은 레이아웃 두 개를 만든다.
#   A = UniversLTStd-BoldCn 15.6 초록 (x 53.9 짝수쪽 / 59.5 홀수쪽): 개념원리 익히기 · 연습문제 · 실력UP
#   B = UniversLTStd-BoldCn 14.0 초록 (x 102 / 107.7, 특강 127.6): 필수예제 아래 확인체크
#   필수예제 번호(Helvetica-Bold 14.2)는 풀이가 붙어 있어 넣지 않음.
# 문제 영역을 끊을 '벽'(STEP 띠, 필수예제 머리)의 y 도 barriers.json 에 적는다 (merge_parts.py 가 아래 끝을 자름).
# python gen_manual.py <pdf> <slug폴더>
import sys, json, re, os
import fitz
sys.stdout.reconfigure(encoding="utf-8")
pdf, root = sys.argv[1:3]
d = fitz.open(pdf)
P0, P1 = 10, 224
A, B, bars, lx = [], [], {}, {}
for pno in range(P0, P1 + 1):
    for bl in d[pno - 1].get_text("dict")["blocks"]:
        for l in bl.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                f, z, (x, y) = s["font"], round(s["size"], 1), s["bbox"][:2]
                if f.startswith("Impact") or (f.startswith("Helvetica-Bold") and z == 14.2):
                    bars.setdefault(pno, []).append([round(y, 1), round(s["bbox"][3], 1)])          # STEP 1/2 띠, 필수예제 머리
                if not re.fullmatch(r"\d{1,3}", t) or not f.startswith("UniversLTStd-BoldCn") or x > 140:
                    continue
                if not (55 <= y <= 675):
                    continue
                m = {"page": pno, "col": 0, "y": round(y, 1), "num": int(t)}
                if z == 15.6 or (z == 14.0 and x < 80):          # (기하) 191쪽 연습문제 173번은 14.0 글자
                    A.append(m)
                elif z == 14.0:
                    B.append(m)
                    lx.setdefault(str(pno), []).append([round(y, 1), round(x, 1)])
for ms in (A, B):
    ms.sort(key=lambda m: (m["page"], m["y"]))
print("A", len(A), "B", len(B))
base = {
    "source": "text",
    "pages": [[P0, P1]],
    "label_regex": "^(x{50})$",
    "groups": False,
    "drop_outliers": False,
    "body": [60, 676],
    "top_pad": 12,
    "bot_pad": 6,
    "gap_stop": 60,
}
la = dict(base, columns=[{"x": [55, 390], "label_x": [0, 1]}],
          columns_even=[{"x": [49, 384], "label_x": [0, 1]}], manual_labels=A)
lb = dict(base, columns=[{"x": [104, 486], "label_x": [0, 1]}],
          columns_even=[{"x": [98.5, 486], "label_x": [0, 1]}], manual_labels=B)
for name, cfg in (("a", la), ("b", lb)):
    json.dump(cfg, open(os.path.join(root, f"layout_{name}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"barriers": bars, "b_label_x": lx}, open(os.path.join(root, "barriers.json"), "w", encoding="utf-8"),
          ensure_ascii=False)
