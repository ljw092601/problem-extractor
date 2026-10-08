# Point 상자(문제 아래 팁) 앞에서 문제 영역 자르기 — problems.json 후처리
import json, re, sys
sys.path.insert(0, r"C:\Users\ljw09\Desktop\promblem_area")
import fitz
from core import winocr

pdf, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
doc = fitz.open(pdf)
data = json.load(open(src, encoding="utf-8"))
probs = data["problems"]
rx = re.compile(r"^P\S{0,3}n?t\b", re.I)
log = []
for p in probs:
    x0, y0, x1, y1 = p["bbox"]
    if y1 - y0 < 60:
        continue
    clip = fitz.Rect(x0, y0 + 20, x0 + 70, y1)
    hits = []
    for dpi in (200, 300, 150):             # 한 해상도에서 못 읽으면 다른 해상도로
        pix = doc[p["pdf_page"]].get_pixmap(dpi=dpi, clip=clip, colorspace=fitz.csGRAY)
        sc = 72 / dpi
        for text, a, b, c, d in winocr.ocr_pixmap(pix):
            t = text.strip()
            if rx.match(t) and len(t) <= 7:
                hits.append((b * sc + clip.y0, t))
        if hits:
            break
    if hits:
        yy, t = min(hits)
        nb = round(yy - 6, 1)
        log.append(f"{p['page']}p #{p['num']} {t!r} bottom {y1} -> {nb}")
        p["bbox"][3] = nb
json.dump(data, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n".join(log))
print("trimmed", len(log))
