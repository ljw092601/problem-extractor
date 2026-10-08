# A(본문 문제, 1단) + B1(중단원 학습 점검) + B2(대단원 학습 평가) + B3(익힘책) 합치기.  (고1 비상교과서_공통수학1 방식 그대로)
# A 는 아래에 붙은 '예제' 상자 / '내 역량' 상자 / 개념 설명 문단(10.6pt 본문 글꼴) 앞에서 끊는다.
# 사용: python merge_postprocess.py <A,B1,B2,B3 extract 결과가 든 폴더 접두사>   (예: ...\scratchpad\go2tb\b1  →  b1A, b1B1, b1B2, b1B3)
import json, re, sys, fitz
sys.path.insert(0, r"C:\Users\ljw09\Desktop\promblem_area")
from core.extract import content_bottom
S = sys.argv[1]
W = r"C:\Users\ljw09\Desktop\promblem_area\work\고2_비상교과서_확률과통계"
PDF = r"C:\Users\ljw09\Desktop\promblem_area\work\_src\고2\교과서\[비상교육] 고등_확률과 통계(김원경)_교과서.pdf"
TOP_PAD_A = 18
HANGUL = re.compile("[가-힣]")


def load(k):
    return json.load(open(S + k + r"\problems.json", encoding="utf-8"))


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
allp = A["problems"] + load("B1")["problems"] + load("B2")["problems"] + load("B3")["problems"]
allp.sort(key=lambda p: (p["page"], 1 if p["column"] == "R" else 0, p["bbox"][1]))
# 중단원 학습 점검 마지막 문제 아래 '문제가 더 필요하면 수학 익힘책 ○쪽으로!' 캐릭터 말풍선 빼기
for p in allp:
    page = doc[p["pdf_page"]]
    x0, y0, x1, y1 = p["bbox"]
    hits = [b for b in page.search_for("문제가 더 필요하면") if x0 - 5 < b.x0 < x1 and y0 < b.y0 < y1]
    if hits:
        cut = min(b.y0 for b in hits) - 12
        words = [w for w in page.get_text("words") if w[0] >= x0 and w[2] <= x1 and y0 < w[1] and w[3] < cut and w[0] < min(b.x0 for b in hits) - 60]
        bot = round(max(w[3] for w in words) + 8, 1)
        log.append(f"{p['page']}쪽 {p['num']}번: {y1}→{bot} (익힘책 말풍선)")
        p["bbox"][3] = bot
for p in allp:
    p["label"] = f"{p['num']:02d}"
json.dump({"pdf": A["pdf"], "problems": allp}, open(W + r"\problems.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("A", len(A["problems"]), "total", len(allp), "잘라낸 것", len(log))
print("\n".join(log))
