# A(본문 문제·예제 함께 추출) + B(중단원 마무리·대단원 평가) + C(대단원 평가 마지막 쪽) + D(준비 학습) 합치기.
# A 에서 번호 색이 예제(파랑 5d9bd3)인 항목은 뺀다 (문제 = 자주 853058). 예제는 앞 문제의 아래 멈춤점 역할만.
import json, os, sys, fitz
sys.path.insert(0, r"C:\Users\ljw09\Desktop\promblem_area")
from core import extract as X

S = r"C:\Users\ljw09\AppData\Local\Temp\claude\C--Users-ljw09-Desktop-promblem-area\c26382be-0e2b-44d9-be28-6fa123aea8e4\scratchpad\mr"
PDF = r"C:\Users\ljw09\Desktop\promblem_area\work\_src\고2\교과서\[미래엔]22개정_고등_미적분1_교과서.pdf"
OUT = r"C:\Users\ljw09\Desktop\promblem_area\work\고2_미래엔교과서_미적분1"
TOP = 14  # layout_A top_pad
d = fitz.open(PDF)


def load(k):
    return json.load(open(os.path.join(S, k, "problems.json"), encoding="utf-8"))["problems"]


def color(p):
    ly = p["bbox"][1] + TOP
    for b in d[p["pdf_page"]].get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if s["text"].strip() == str(p["num"]) and 14.0 <= s["size"] <= 14.6 and abs(s["bbox"][1] - ly) < 4:
                    return f'{s["color"]:06x}'
    return None


FIX_BOTTOM = {     # (쪽, 번호): 아래끝 — 아래 설명·활동 상자·자기 평가 표가 딸려 오는 것 끊기
    (106, 2): 482.0,   # 아래 '생각 넓히기' 활동
    (128, 1): 578.0,   # 아래 본문 '한편, a>=b 일 때…' 와 정의 상자
    (115, 21): 360.0,  # 대단원 평가 아래 '자기 평가' 표
    (160, 21): 256.0,  # (가)(나) 조건 상자 아랫선까지
}
CONT = []         # 이어지는 조각: dict(page, pdf_page, column, bbox, num)
keepA, log = [], []
for p in load("A"):
    c = color(p)
    if c == "853058":
        p["column"] = "L"
        keepA.append(p)
    else:
        log.append(f"A 제외: {p['page']}쪽 {p['num']} (색 {c})")
D = load("D")
for p in D:
    p["column"] = "L"
allp = keepA + load("B") + load("C") + D
for p in allp:
    if (p["page"], p["num"]) in FIX_BOTTOM:
        p["bbox"][3] = FIX_BOTTOM[(p["page"], p["num"])]
        log.append(f"{p['page']}쪽 {p['num']}번 아래끝 {p['bbox'][3]}")
for c in CONT:
    q = dict(c); q["continued"] = True; q.setdefault("label", str(q["num"]))
    allp.append(q)
allp.sort(key=lambda p: (p["page"], 1 if p["column"] == "R" else 0, p["bbox"][1]))
with open(os.path.join(OUT, "problems.json"), "w", encoding="utf-8") as f:
    json.dump({"pdf": os.path.basename(PDF), "problems": allp}, f, ensure_ascii=False, indent=1)
print("\n".join(log))
print("A", len(keepA), "합계", len(allp))
if "--sheets" in sys.argv:
    paths = X.contact_sheets(PDF, allp, os.path.join(S, "sheets"))
    print(len(paths), "sheets")
