# -*- coding: utf-8 -*-
"""쎈B: 각 쪽 OCR 토큰에서 (1) 2자리 문제 번호 후보, (2) 오른쪽 위 '쎈 0050' 대응 번호를 모아 JSON 으로 저장.
    python refs.py <pdf> <first> <last> <out.json>"""
import json, os, re, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
sys.path.insert(0, ROOT)
import fitz
from core import extract as X

pdf, a, b, out = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
d = fitz.open(pdf)
cfg = {"source": "ocr", "ocr_dpi": [150, 200], "body": None}
res = {}
for p in range(a, b + 1):
    page = d[p - 1]
    W = page.rect.width
    toks = X._ocr_tokens(page, cfg)
    labs, refs = [], []
    for text, bb, size in toks:
        m = re.search(r"(\d{4})$", text)
        if m and size < 10 and (200 < bb[0] < W / 2 - 2 or bb[0] > W - 110):
            refs.append([int(m.group(1)), round(bb[0], 1), round(bb[1], 1)])
        m = re.fullmatch(r"(\d{2})", text)
        if m and size >= 9.5 and (40 < bb[0] < 85 or 305 < bb[0] < 350):
            labs.append([int(m.group(1)), round(bb[0], 1), round(bb[1], 1), round(size, 1)])
    res[p] = {"labs": labs, "refs": refs}
    print(p, len(labs), len(refs), flush=True)
json.dump(res, open(out, "w"), indent=0)
