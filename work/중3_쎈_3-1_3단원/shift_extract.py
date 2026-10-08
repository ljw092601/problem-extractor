# -*- coding: utf-8 -*-
"""쪽마다 좌우 밀림(dx)이 다른 스캔본용: core.extract 를 고치지 않고, 실행 중에만
columns_for 를 바꿔 쪽별로 단 좌표를 dx 만큼 옮겨서 추출한다.
    python shift_extract.py <pdf> <layout.json> <out_dir> [--pages 7-20] [--no-sheets] [--dx dx.json]
layout.json 의 columns 는 기준(dx=0) 좌표. "shift_ref": [L, R] = 기준 좌/우 단 번호 x.
쪽별 dx 는 OCR 번호 x 로 자동 측정 (--dx 로 고정값 파일을 주면 그것을 씀) → out_dir/page_dx.json 에 저장.
"""
import json, os, re, sys, statistics
sys.path.insert(0, os.getcwd())
import fitz
from core import extract as X
import book_tool

pdf, lay, out = sys.argv[1:4]
args = sys.argv[4:]
only = book_tool.parse_pages(args[args.index("--pages") + 1]) if "--pages" in args else None
sheets = "--no-sheets" not in args
fixed = json.load(open(args[args.index("--dx") + 1], encoding="utf-8")) if "--dx" in args else {}
fixed = {int(k): v for k, v in fixed.items()}

cfg = X.load_layout(lay)
L, R = cfg["shift_ref"]
base_cols = cfg["columns"]
cache = {}
orig_ocr = X._ocr_page


def ocr_cached(page, c):
    key = (page.parent.name, page.number, tuple(c["ocr_dpi"]))
    if key not in cache:
        cache[key] = orig_ocr(page, c)
    return cache[key]


X._ocr_page = ocr_cached
doc = fitz.open(pdf)
rx = re.compile(r"^(?:[01]\d{3}|\[[01]\d{3})")
dxs = {}


def measure(pno):
    toks = ocr_cached(doc[pno], cfg)[0]
    ds = []
    for t, b, h in toks:
        if not rx.match(t) or h < 8:
            continue
        if L - 40 <= b[0] <= L + 25:
            ds.append(b[0] - L)
        elif R - 40 <= b[0] <= R + 25:
            ds.append(b[0] - R)
    return ds


def page_dx(pno):
    if pno + 1 in fixed:
        return fixed[pno + 1]
    if pno not in dxs:
        ds = measure(pno)
        dxs[pno] = round(min(ds) if len(ds) < 3 else statistics.median(sorted(ds)[:max(3, len(ds) // 2)]), 1) if ds else None
    return dxs[pno]


def nearest(pno):
    for k in range(1, 20):
        for q in (pno - 2 * k, pno + 2 * k, pno - k, pno + k):   # 같은 홀짝 먼저
            if 0 <= q < doc.page_count and page_dx(q) is not None:
                return page_dx(q)
    return 0


def columns_for(c, pno):
    d = page_dx(pno)
    if d is None:
        d = nearest(pno)
    used[pno + 1] = d
    return [{"x": [col["x"][0] + d, col["x"][1] + d], "label_x": [col["label_x"][0] + d, col["label_x"][1] + d]}
            for col in base_cols]


used = {}
X.columns_for = columns_for
problems, rep = X.extract(pdf, cfg, only, progress=lambda k, n, p, c: print(f"\r  {k}/{n} ({p}쪽 dx={used.get(p)})", end="", flush=True))
print()
os.makedirs(out, exist_ok=True)
w = doc[0].rect.width
for p in problems:                                           # 쪽 밖으로 나가지 않게
    p["bbox"][0] = max(0, p["bbox"][0]); p["bbox"][2] = min(round(w, 1), p["bbox"][2])
json.dump({"pdf": os.path.basename(pdf), "problems": problems}, open(os.path.join(out, "problems.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
txt = X.report_text(rep)
open(os.path.join(out, "report.txt"), "w", encoding="utf-8").write(txt)
json.dump({str(k): v for k, v in sorted(used.items())}, open(os.path.join(out, "page_dx.json"), "w", encoding="utf-8"))
print(txt)
print("dx:", sorted(used.items()))
if sheets:
    X.contact_sheets(pdf, problems, os.path.join(out, "sheets"))
