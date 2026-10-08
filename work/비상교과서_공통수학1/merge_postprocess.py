# A(본문 문제, 1단) + B1(중단원 학습 점검) + B2(대단원 학습 평가·익힘책) 합치기.
# A 는 아래에 붙은 '예제' 상자 / '내 역량' 상자 / 개념 설명 문단(10.6pt 본문 글꼴) 앞에서 끊는다.
import json, re, sys, fitz
sys.path.insert(0, r"C:\Users\ljw09\Desktop\promblem_area")
from core.extract import content_bottom
S = r"C:\Users\ljw09\AppData\Local\Temp\claude\C--Users-ljw09-Desktop-promblem-area\c26382be-0e2b-44d9-be28-6fa123aea8e4\scratchpad\bs1"
W = r"C:\Users\ljw09\Desktop\promblem_area\work\비상교과서_공통수학1"
PDF = r"C:\Users\ljw09\Desktop\promblem_area\work\_src\고1\교과서\비상\비상 공통수학1(김원경) 교과서.pdf"
TOP_PAD_A = 18
HANGUL = re.compile("[가-힣]")


def load(k):
    return json.load(open(S + "\\" + k + r"\problems.json", encoding="utf-8"))


def stoppers(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            spans = [s for s in l["spans"] if s["text"].strip()]
            if not spans:
                continue
            t = "".join(s["text"] for s in spans).strip()
            y0, x0 = l["bbox"][1], l["bbox"][0]
            if t == "예제":
                out.append((y0 - 16, "예제"))
            elif t.startswith("내 역량"):
                out.append((y0 - 14, "내역량"))
            elif x0 >= 140 and HANGUL.search(t) and min(s["size"] for s in spans) >= 10.55:
                out.append((y0 - 6, "설명:" + t[:15]))
    return out


A = load("A")
doc = fitz.open(PDF)
log = []
for p in A["problems"]:
    p["column"] = "L"
    page = doc[p["pdf_page"]]
    x0, y0, x1, y1 = p["bbox"]
    lab = y0 + TOP_PAD_A
    st = [s for s in stoppers(page) if lab + 12 < s[0] < y1]
    if st:
        lim, why = min(st)
        gray = page.get_pixmap(dpi=100, colorspace=fitz.csGRAY)
        bot = min(lim, content_bottom(gray, 100 / 72, x0, x1, y0, lim, 35) + 6)
        log.append(f"{p['page']}쪽 {p['num']}번: {y1}→{round(bot, 1)} ({why})")
        p["bbox"][3] = round(bot, 1)
allp = A["problems"] + load("B1")["problems"] + load("B2")["problems"]
allp.sort(key=lambda p: (p["page"], 1 if p["column"] == "R" else 0, p["bbox"][1]))
for p in allp:
    p["label"] = f"{p['num']:02d}"
json.dump({"pdf": A["pdf"], "problems": allp}, open(W + r"\problems.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("total", len(allp), "잘라낸 것", len(log))
print("\n".join(log))
