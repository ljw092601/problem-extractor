# 묶음 머리글 '[' (초록) 찾기 + 머리글 조각 OCR 로 범위 읽기
import fitz, json, re, sys
sys.path.insert(0, r"C:\Users\ljw09\Desktop\promblem_area")
from core import winocr
S = r"C:\Users\ljw09\AppData\Local\Temp\claude\C--Users-ljw09-Desktop-promblem-area\c26382be-0e2b-44d9-be28-6fa123aea8e4\scratchpad\rpm"
d = fitz.open(S + r"\clean\22개정 RPM 미적분1 학생용 1.pdf")
ml = json.load(open(S + r"\ml.json"))
out = []
for pno in range(6, 134):
    pg = d[pno]
    for dr in pg.get_drawings():
        f = dr.get("fill"); r = dr["rect"]
        if not f or abs(f[0] - 0.0106) > 0.02 or abs(f[1] - 0.609) > 0.02:
            continue
        if not (r.width < 3.2 and 7.5 < r.height < 9.8):
            continue
        even = (pno + 1) % 2 == 0
        lx = [(46, 53), (311, 318)] if even else [(55, 62), (319, 327)]
        ci = next((i for i, (a, b) in enumerate(lx) if a - 2 <= r.x0 <= b), None)
        if ci is None:
            continue
        clip = fitz.Rect(r.x0 - 2, r.y0 - 3, r.x0 + 75, r.y1 + 3)
        pix = pg.get_pixmap(dpi=400, clip=clip, colorspace=fitz.csGRAY)
        txt = " ".join(t for t, *_ in winocr.ocr_pixmap(pix))
        nums = [int(x) for x in re.findall(r"\d{3,4}", txt)]
        below = sorted([m for m in ml if m["page"] == pno + 1 and m["col"] == ci and m["y"] > r.y0], key=lambda m: m["y"])
        a = below[0]["num"] if below else None
        out.append({"page": pno + 1, "col": ci, "y": round(r.y0, 1), "ocr": txt, "nums": nums, "next": a})
json.dump(out, open(S + r"\vg.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
for o in out:
    print(o["page"], o["col"], o["y"], o["ocr"], o["next"])
print(len(out))
