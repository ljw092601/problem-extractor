import json, os, sys, fitz
sys.path.insert(0, r"C:\Users\ljw09\Desktop\promblem_area")
from core import extract as X

S = os.path.dirname(os.path.abspath(__file__))
PDF = r"C:\Users\ljw09\Desktop\promblem_area\work\_src\고1\교과서\미래엔\미래엔(황선욱) 공통수학2 교과서 원본.pdf"
OUT = r"C:\Users\ljw09\Desktop\promblem_area\work\미래엔교과서_공통수학2"
d = fitz.open(PDF)
A = json.load(open(os.path.join(S, "A", "problems.json"), encoding="utf-8"))["problems"]
B = json.load(open(os.path.join(S, "B", "problems.json"), encoding="utf-8"))["problems"]
TOP = 14  # layout_A top_pad


def kind(p):
    """라벨 왼쪽의 '문제' / '예제' 글자"""
    ly = p["bbox"][1] + TOP
    for b in d[p["pdf_page"]].get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if t in ("문제", "예제") and 140 <= s["bbox"][0] <= 215 and abs(s["bbox"][1] - ly) < 10:
                    return t
    return None


keepA, log = [], []
for p in A:
    k = kind(p)
    if k == "문제":
        keepA.append(p)
    else:
        log.append(f"A 제외: {p['page']}쪽 {p['num']} ({k})")
# 131쪽: 문제 7 소문제 줄의 근호 조각 '5'(크기 14.3)가 번호로 잡혀 문제 7이 잘림 → 합침
for p in keepA:
    if p["page"] == 131 and p["num"] == 7:
        p["bbox"][3] = 712.0
        log.append("131쪽 문제 7 아래끝 712 로 수정")
FIX_BOTTOM = {(72, 5): 484.0}   # 72쪽 문제 5: 아래 본문('이상으로부터…', y=490)·연산법칙 상자가 딸려 옴
for p in keepA:
    if (p["page"], p["num"]) in FIX_BOTTOM:
        p["bbox"][3] = FIX_BOTTOM[(p["page"], p["num"])]
        log.append(f"{p['page']}쪽 문제 {p['num']} 아래끝 {p['bbox'][3]} 로 수정")
allp = keepA + B
allp.sort(key=lambda p: (p["page"], 1 if p["column"] == "R" else 0, p["bbox"][1]))
with open(os.path.join(OUT, "problems.json"), "w", encoding="utf-8") as f:
    json.dump({"pdf": os.path.basename(PDF), "problems": allp}, f, ensure_ascii=False, indent=1)
print("\n".join(log))
print("A", len(keepA), "B", len(B), "합계", len(allp))
if "--sheets" in sys.argv:
    paths = X.contact_sheets(PDF, allp, os.path.join(S, "sheets"))
    print(len(paths), "sheets")
