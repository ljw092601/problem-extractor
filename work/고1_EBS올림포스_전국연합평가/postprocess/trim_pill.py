# Point 알약(짙은 청회색 둥근 띠) 픽셀로 찾아 그 위에서 문제 자르기 — problems.json 후처리
import json, sys
import fitz

pdf, src, dst = sys.argv[1], sys.argv[2], sys.argv[3]
doc = fitz.open(pdf)
data = json.load(open(src, encoding="utf-8"))
log = []
for p in data["problems"]:
    x0, y0, x1, y1 = p["bbox"]
    if y1 - y0 < 50:
        continue
    clip = fitz.Rect(x0 + 2, y0 + 25, x0 + 70, y1)
    pix = doc[p["pdf_page"]].get_pixmap(dpi=72, clip=clip)
    rows = []
    for yy in range(pix.height):
        best = cur = 0
        for xx in range(pix.width):
            r, g, b = pix.pixel(xx, yy)[:3]
            if b - r >= 15 and r < 0x90 and b < 0xb0:
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
        rows.append(best >= 16)
    hit = None
    for yy, ok in enumerate(rows):          # 알약 위·아래 테두리: 5~12pt 간격으로 두 줄
        if ok and any(rows[yy + k] for k in range(5, 13) if yy + k < len(rows)):
            hit = clip.y0 + yy - 1
            break
    if hit is not None:
        nb = round(hit - 5, 1)
        log.append(f"{p['page']}p #{p['num']} bottom {y1} -> {nb}")
        p["bbox"][3] = nb
json.dump(data, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n".join(log))
print("trimmed", len(log))
