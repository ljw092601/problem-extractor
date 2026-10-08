# 비상 미적분Ⅰ 교과서 분책(1·2·3) 공통 합치기: A(본문 문제, 1단) + B1(중단원 학습 점검) + B2(대단원 학습 평가·익힘책)
# + B3(대단원 학습 평가 마지막 쪽, 아래 스스로 돌아보는 나의 학습 제외) + B4(수학 익힘책) + D(중단원 첫 쪽 준비 학습).
# A 는 아래에 붙은 '예제' 상자 / '내 역량' 상자 / 개념 설명 문단(10.6pt 본문 글꼴) 앞에서 끊는다.
#   python merge_postprocess.py <권 번호 1|2|3> [--sheets]
import json, os, re, sys, fitz
sys.path.insert(0, r"C:\Users\ljw09\Desktop\promblem_area")
from core.extract import content_bottom

V = sys.argv[1]
S = r"C:\Users\ljw09\AppData\Local\Temp\claude\C--Users-ljw09-Desktop-promblem-area\c26382be-0e2b-44d9-be28-6fa123aea8e4\scratchpad\bs2\v" + V
W = r"C:\Users\ljw09\Desktop\promblem_area\work\고2_비상교과서_미적분1_" + V
PDF = r"C:\Users\ljw09\Desktop\promblem_area\work\_src\고2\교과서\[비상교육] 고등_미적분Ⅰ_" + V + "_교과서.pdf"
TOP_PAD_A = 18
HANGUL = re.compile("[가-힣]")
FIX = json.load(open(os.path.join(W, "fix.json"), encoding="utf-8")) if os.path.exists(os.path.join(W, "fix.json")) else {}
# fix.json: {"bottom": {"쪽-번호": y}, "continued": [{"page":.., "column": "L", "bbox": [..], "num": ..}]}


def load(k):
    return json.load(open(os.path.join(S, k, "problems.json"), encoding="utf-8"))["problems"]


def stoppers(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            spans = [s for s in l["spans"] if s["text"].strip()]
            if not spans:
                continue
            t = "".join(s["text"] for s in spans).strip()
            y0, x0 = l["bbox"][1], l["bbox"][0]
            if t == "예제" or (spans[0]["size"] > 17.5 and spans[0]["color"] == 0xffffff and t.isdigit()):
                out.append((y0 - 16, "예제"))
            elif t.startswith("내 역량"):
                out.append((y0 - 14, "내역량"))
            elif x0 >= 140 and HANGUL.search(t) and min(s["size"] for s in spans) >= 10.55:
                out.append((y0 - 6, "설명:" + t[:15]))
    return out


doc = fitz.open(PDF)
log = []
A = load("A")
for p in A:
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
D = load("D")
for p in D:
    p["column"] = "L"
B1 = load("B1")
for p in B1:
    # 중단원 학습 점검 첫 쪽 오른쪽 단 첫 문제 위의 안내 문장('문제를 풀고, 개념을 이해했는지 …')이 top_pad 안에 들면 그 아래로
    x0, y0, x1, y1 = p["bbox"]
    for b in doc[p["pdf_page"]].get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = "".join(s["text"] for s in l["spans"])
            if "문제를 풀고" in t and y0 - 2 < l["bbox"][3] < y0 + 14 and l["bbox"][2] > x0 and l["bbox"][0] < x1:
                p["bbox"][1] = round(l["bbox"][3] + 1, 1)
                log.append(f"{p['page']}쪽 {p['num']}번 위끝 → {p['bbox'][1]} (안내 문장 제외)")
allp = A + B1 + load("B2") + load("B3") + load("B4") + D
for p in allp:
    k = f"{p['page']}-{p['num']}"
    if k in FIX.get("bottom", {}):
        p["bbox"][3] = FIX["bottom"][k]
        log.append(f"수동: {k} 아래끝 {p['bbox'][3]}")
for c in FIX.get("continued", []):
    q = dict(c)
    q["continued"] = True
    q["pdf_page"] = q["page"] - 1
    allp.append(q)
    log.append(f"이어짐: {q['page']}쪽 {q['num']}번 조각")
allp.sort(key=lambda p: (p["page"], 1 if p["column"] == "R" else 0, p["bbox"][1]))
for p in allp:
    p["label"] = f"{p['num']:02d}"
json.dump({"pdf": os.path.basename(PDF), "problems": allp}, open(os.path.join(W, "problems.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("total", len(allp), "잘라낸 것", len(log))
print("\n".join(log))

if "--sheets" in sys.argv:
    # CropBox 가 밀린 PDF 라 도구의 contact_sheets 대신 page.get_pixmap(clip=bbox) 로 직접 자름
    from PIL import Image, ImageDraw
    out = os.path.join(S, "sheets")
    os.makedirs(out, exist_ok=True)
    per, W0 = 12, 900
    for si in range(0, len(allp), per):
        chunk = allp[si:si + per]
        tiles = []
        for p in chunk:
            pg = doc[p["pdf_page"]]
            pix = pg.get_pixmap(dpi=90, clip=fitz.Rect(p["bbox"]))
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            tiles.append((p, im))
        col_w = W0 // 3
        rows = [tiles[i:i + 3] for i in range(0, len(tiles), 3)]
        H = sum(max(min(t[1].height, 420) for t in r) + 22 for r in rows)
        sheet = Image.new("RGB", (W0, H), "white")
        dr = ImageDraw.Draw(sheet)
        y = 0
        for r in rows:
            h = max(min(t[1].height, 420) for t in r)
            for i, (p, im) in enumerate(r):
                sc = min(1, (col_w - 8) / im.width)
                im2 = im.resize((int(im.width * sc), int(im.height * sc)))
                im2 = im2.crop((0, 0, im2.width, min(im2.height, 420)))
                dr.text((i * col_w + 4, y + 4), f"{p['page']}p #{p['num']}" + (" (이어짐)" if p.get("continued") else ""), fill="red")
                sheet.paste(im2, (i * col_w + 4, y + 18))
                dr.rectangle([i * col_w + 4, y + 18, i * col_w + 4 + im2.width, y + 18 + im2.height], outline="blue")
            y += h + 22
        sheet.save(os.path.join(out, f"sheet_{si // per + 1:03d}.png"))
    print("sheets", (len(allp) + per - 1) // per, out)
