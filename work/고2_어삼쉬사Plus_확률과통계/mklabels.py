"""조각난 번호(00+1)를 이어 붙여 manual_labels 생성.
usage: mklabels.py pdf size_lo size_hi pages(a-b,c-d) split_x out.json
split_x: 'even_split,odd_split' — x 가 이 값보다 크면 col 1"""
import sys, fitz, re, json
pdf, lo, hi, prange, split, outp = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6]
se, so = map(float, split.split(','))
pages = []
for part in prange.split(','):
    a, b = part.split('-'); pages += list(range(int(a), int(b) + 1))
doc = fitz.open(pdf)
labels = []
for p in pages:
    page = doc[p - 1]
    spans = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if t and lo <= s["size"] <= hi and re.fullmatch(r"\d+", t):
                    spans.append([s["bbox"][0], s["bbox"][1], s["bbox"][2], s["bbox"][3], t])
    spans.sort(key=lambda s: (round(s[1]), s[0]))
    merged = []
    for s in spans:
        if merged and abs(merged[-1][1] - s[1]) < 2 and -1 <= s[0] - merged[-1][2] < 6:
            merged[-1][2] = s[2]; merged[-1][4] += s[4]
        else:
            merged.append(list(s))
    sp = se if p % 2 == 0 else so
    for m in merged:
        labels.append({"page": p, "col": 1 if m[0] > sp else 0, "y": round(m[1], 1), "num": int(m[4])})
labels.sort(key=lambda d: (d["page"], d["col"], d["y"]))
json.dump(labels, open(outp, "w", encoding="utf-8"))
print(len(labels))
