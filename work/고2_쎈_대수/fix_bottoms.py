# -*- coding: utf-8 -*-
"""뒷면 비침(흐린 잉크) 때문에 다음 번호 바로 위까지 늘어난 영역의 아래 끝을 다시 잡는다.
python fix_bottoms.py <pdf> <in problems.json> <out problems.json> <spec.json>
spec: [{"page": 12, "label": "0052", "bottom": 560}  (bottom 직접 지정)
       {"page": 142, "label": "0981", "auto": true}]  (진한 잉크(<100)만 보고 gap 30pt 에서 멈춤, +12)"""
import json, sys
import fitz

pdf, src, dst, spec = sys.argv[1:5]
d = json.load(open(src, encoding="utf-8"))
sp = json.load(open(spec, encoding="utf-8"))
doc = fitz.open(pdf)
for s in sp:
    p = next(q for q in d["problems"] if q["page"] == s["page"] and q["label"] == s["label"] and not q.get("continued"))
    x0, y0, x1, y1 = p["bbox"]
    if "bottom" in s:
        nb = s["bottom"]
    else:
        pix = doc[p["pdf_page"]].get_pixmap(dpi=100, colorspace=fitz.csGRAY)
        sc = 100 / 72
        px0, px1 = int(x0 * sc), int(x1 * sc)
        last, blank, started = int(y0 * sc), 0, False
        for ry in range(int(y0 * sc), int(y1 * sc)):
            row = pix.samples[ry * pix.stride + px0: ry * pix.stride + px1]
            if min(row) < 100:
                last, blank, started = ry, 0, True
            elif started:
                blank += 1
                if blank >= 30 * sc:
                    break
        nb = round(min(y1, last / sc + 12), 1)
    print(s["page"], s["label"], y1, "->", nb)
    p["bbox"] = [x0, y0, x1, nb]
json.dump(d, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
