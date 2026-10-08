import sys, json, re, fitz
sys.path.insert(0, r"C:\Users\ljw09\Desktop\promblem_area")
from core import extract as X
# blabels.py pdf out.json spec...   spec = "a-b:layout.json" (page range -> layout for column geometry)
# Detect colored blobs at column-left (problem numbers: orange/green/blue; instruction icons: light green bubble),
# attach OCR digits from page tokens.
DPI = 144
pdf, out = sys.argv[1], sys.argv[2]
specs = []
for s in sys.argv[3:]:
    rng, lay = s.split(":", 1)
    a, b = map(int, rng.split("-"))
    specs.append((a, b, X.load_layout(lay)))

def cols_for(cfg, p):
    return cfg["columns_even"] if p % 2 == 0 and cfg.get("columns_even") else cfg["columns"]

def colored(r, g, b):
    return max(r, g, b) - min(r, g, b) > 28 and min(r, g, b) < 190

d = fitz.open(pdf)
res = []
for a, b, cfg in specs:
    body = cfg["body"]
    for p in range(a, b + 1):
        page = d[p - 1]
        toks = None
        cols = cols_for(cfg, p)
        blobs = []
        for ci, c in enumerate(cols):
            x0 = c["label_x"][0] - 4
            x1 = c["label_x"][0] + 30
            clip = fitz.Rect(x0, body[0], x1, body[1])
            pix = page.get_pixmap(dpi=DPI, clip=clip)
            w, h, s, st = pix.width, pix.height, pix.samples, pix.stride
            rows = []
            for y in range(h):
                xs = []; sr = sg = sb = 0
                for x in range(w):
                    i = y * st + x * 3
                    R, G, B = s[i], s[i + 1], s[i + 2]
                    if colored(R, G, B):
                        xs.append(x); sr += R; sg += G; sb += B
                rows.append((xs, sr, sg, sb))
            runs = []
            y = 0
            while y < h:
                if rows[y][0]:
                    y2 = y; gap = 0; last = y
                    while y2 < h and gap <= 1:
                        if rows[y2][0]:
                            gap = 0; last = y2
                        else:
                            gap += 1
                        y2 += 1
                    runs.append((y, last))
                    y = y2
                else:
                    y += 1
            def split(a, b2):
                # split tall runs (tag merged with label) at the sparsest row
                if (b2 - a + 1) * 72 / DPI <= 14.5:
                    return [(a, b2)]
                lo, hi = a + int(4 * DPI / 72), b2 - int(4 * DPI / 72)
                if lo >= hi:
                    return [(a, b2)]
                r = min(range(lo, hi + 1), key=lambda k: len(rows[k][0]))
                if len(rows[r][0]) > 3:
                    return [(a, b2)]
                return split(a, r - 1) + split(r + 1, b2)
            segs = []
            for a, b2 in runs:
                segs += split(a, b2)
            for y, last in segs:
                while y <= last and not rows[y][0]:
                    y += 1
                while last >= y and not rows[last][0]:
                    last -= 1
                if last < y:
                    continue
                allx = []; SR = SG = SB = 0
                for k in range(y, last + 1):
                    allx += rows[k][0]; SR += rows[k][1]; SG += rows[k][2]; SB += rows[k][3]
                n = len(allx)
                bh = (last - y + 1) * 72 / DPI
                bx0 = x0 + min(allx) * 72 / DPI
                bw = (max(allx) - min(allx) + 1) * 72 / DPI
                top = body[0] + y * 72 / DPI
                if 5 <= bh <= 15 and bw >= 5 and bx0 <= c["label_x"][1] + 2:
                    blobs.append({"page": p, "col": ci, "y": round(top, 1), "h": round(bh, 1), "w": round(bw, 1),
                                  "x": round(bx0, 1), "rgb": [SR // n, SG // n, SB // n], "fill": round(n / ((last - y + 1) * (max(allx) - min(allx) + 1)), 2)})
        if True:
            toks = X.page_content(page, cfg)[0]
            for ci, c in enumerate(cols):
                for t, bb, sz in toks:
                    tt = t.strip().replace("O", "0").replace("o", "0")
                    if re.fullmatch(r"\d{1,2}", tt) and c["label_x"][0] - 6 <= bb[0] <= c["label_x"][1] + 4 and body[0] <= bb[1] <= body[1]:
                        res.append({"tok": True, "page": p, "col": ci, "y": round(bb[1], 1), "x": round(bb[0], 1), "num": int(tt), "size": round(sz, 1)})
            for bl in blobs:
                cands = []
                for t, bb, sz in toks:
                    tt = t.strip().replace("O", "0").replace("o", "0")
                    if re.fullmatch(r"\d{1,2}", tt) and abs(bb[1] - bl["y"]) <= 6 and bl["x"] - 6 <= bb[0] <= bl["x"] + 8:
                        cands.append(int(tt))
                bl["ocr"] = cands
            res += blobs
        print(p, len(blobs), flush=True)
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False)

