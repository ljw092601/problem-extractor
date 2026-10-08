# -*- coding: utf-8 -*-
"""core.extract 를 그대로 쓰는 실행기 (저장소 코드는 고치지 않음). 중3 작업에서 추가.
  - OCR 결과를 캐시 (다시 돌릴 때 빠르게)
  - 번호 거르기: layout.json 의 "label_filter": "color" 이면, OCR 이 찾은 번호 후보 중
    글자색이 컬러(주황·초록·파랑)인 것만 번호로 인정 → 보기 ①②, 표 숫자(검정)를 번호로 잘못 읽는 것을 막음.
    ("label_color_min" 컬러 픽셀 비율 기본 0.35, "label_color_diff" 채도 기준 기본 22)
    manual_labels 는 거르지 않음.
  - "drop_labels": [{"page": p, "num": n}] 잘못 잡힌 번호 빼기
  - "auto_continued": true 이면 단 맨 위(첫 번호 위)에 내용이 있으면 앞 문제의 이어진 조각으로 보고
    별도 항목 + "continued": true 로 넣음 (번호 = 앞 문제). "continued_min_h" 기본 12pt,
    "continued_skip": [1, [5, "R"]] 이 쪽(·단)은 이어진 조각 찾지 않음
usage: python filter_extract.py <pdf> <layout.json> --out D [--pages ..] [--no-sheets] [--filter NAME]
"""
import sys, os, json, hashlib, pickle, argparse
sys.path.insert(0, r"C:\Users\ljw09\Desktop\promblem_area")
import fitz
from core import extract as X

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocrcache")
os.makedirs(CACHE, exist_ok=True)

_orig_ocr_page = X._ocr_page
_orig_rescue = X._rescue_tokens


def _key(page, *parts):
    doc = page.parent
    h = hashlib.md5((doc.name + "|" + str(page.number) + "|" + repr(parts)).encode("utf-8")).hexdigest()
    return os.path.join(CACHE, h + ".pkl")


def cached_ocr_page(page, cfg):
    k = _key(page, "ocr", tuple(cfg.get("body") or []), tuple(cfg["ocr_dpi"]))
    if os.path.exists(k):
        return pickle.load(open(k, "rb"))
    r = _orig_ocr_page(page, cfg)
    pickle.dump(r, open(k, "wb"))
    return r


def cached_rescue(page, cfg, cols, body):
    k = _key(page, "rescue", tuple(body), tuple(tuple(c["label_x"]) for c in cols))
    if os.path.exists(k):
        return pickle.load(open(k, "rb"))
    r = _orig_rescue(page, cfg, cols, body)
    pickle.dump(r, open(k, "wb"))
    return r


X._ocr_page = cached_ocr_page
X._rescue_tokens = cached_rescue

# ---------- label filters -------------------------------------------------
_orig_page_labels = X.page_labels
FILTER = None
DROPPED = []


def dark_frac(page, rect, dpi=300):
    pix = page.get_pixmap(dpi=dpi, clip=rect, colorspace=fitz.csGRAY)
    s = pix.samples
    n = len(s)
    if n == 0:
        return 0
    return sum(1 for b in s if b < 140) / n


def filt_hollow0(page, d):
    """real label: two digits, the first glyph (a '0' or '1'/'2') ... drop circled choices:
    for labels starting with '0', the centre of the first glyph must be blank (a real '0'),
    a circled number (①②…) has a digit stroke inside."""
    if not d["label"].startswith("0") or d.get("x", 0) == 0:
        return True
    x0, y0, y1 = d["x"], d["y0"], d["y1"]
    h = y1 - y0
    w = h * 0.62  # approx width of one digit glyph
    cx, cy = x0 + w * 0.5, (y0 + y1) / 2
    r = fitz.Rect(cx - w * 0.12, cy - h * 0.14, cx + w * 0.12, cy + h * 0.14)
    return dark_frac(page, r) < 0.08


def color_frac(page, rect, dpi=200):
    pix = page.get_pixmap(dpi=dpi, clip=rect, colorspace=fitz.csRGB, alpha=False)
    s = pix.samples
    ink = col = 0
    for i in range(0, len(s), 3):
        r, g, b = s[i], s[i + 1], s[i + 2]
        mx, mn = max(r, g, b), min(r, g, b)
        if mn > 200:
            continue          # white / paper
        ink += 1
        if mx - mn > COLOR_DIFF:
            col += 1
    return (col / ink) if ink else 0, ink


def filt_color(page, d):
    """real label is printed in colour (orange/green/blue); choices ①② and table digits are black."""
    if d.get("x", 0) == 0:
        return True
    h = d["y1"] - d["y0"]
    r = fitz.Rect(d["x"], d["y0"], d["x"] + h * 1.1, d["y1"])
    f, ink = color_frac(page, r)
    return f > COLOR_MIN


COLOR_MIN = 0.35
COLOR_DIFF = 22
FILTERS = {"hollow0": filt_hollow0, "color": filt_color}


def page_labels(page, cfg, pno=None, prev_last=None, info=None, toks=None, covered=()):
    labels = _orig_page_labels(page, cfg, pno, prev_last, info, toks, covered)
    if FILTER:
        keep = []
        for d in labels:
            if FILTER(page, d):
                keep.append(d)
            else:
                DROPPED.append((page.number + 1, d["label"], round(d["y0"])))
        labels = keep
    return labels


X.page_labels = page_labels


def parse_pages(s):
    out = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def ink_span(gray, sc, x0, x1, y0, y1, thr=150):
    """first and last ink row (pt) in the box, or None"""
    px0, px1 = max(0, int(x0 * sc)), min(gray.width, int(x1 * sc))
    first = last = None
    s, st = gray.samples, gray.stride
    for ry in range(max(0, int(y0 * sc)), min(gray.height, int(y1 * sc))):
        row = s[ry * st + px0: ry * st + px1]
        if min(row, default=255) < thr:
            if first is None:
                first = ry
            last = ry
    return None if first is None else (first / sc, last / sc)


def add_continued(pdf, cfg, problems, only=None):
    """"auto_continued": true -> content at the top of a column above its first label
    (or a whole column without labels) is the rest of the previous problem -> separate item, continued: true."""
    doc = fitz.open(pdf)
    pages = X.page_list(cfg, doc.page_count, only)
    body = cfg["body"]
    out = []
    added = []
    bypage = {}
    for p in problems:
        bypage.setdefault(p["pdf_page"], []).append(p)
    prev = None
    for pno in pages:
        cols = X.columns_for(cfg, pno)
        names = ["LR"[i] if len(cols) == 2 else str(i) for i in range(len(cols))]
        gray = doc[pno].get_pixmap(dpi=100, colorspace=fitz.csGRAY)
        sc = 100 / 72
        items = bypage.get(pno, [])
        for ci, c in enumerate(cols):
            mine = [p for p in items if p["column"] == names[ci]]
            limit = min([p["bbox"][1] for p in mine], default=body[1]) - 2
            skip = [tuple(v) if isinstance(v, list) else (v, None) for v in cfg.get("continued_skip", [])]
            if (pno + 1, None) in skip or (pno + 1, names[ci]) in skip:
                pass
            elif prev is not None and prev["pdf_page"] >= pno - 1 and limit - body[0] > 12:
                sp = ink_span(gray, sc, c["x"][0], c["x"][1], body[0], limit)
                if sp and sp[1] - sp[0] > cfg.get("continued_min_h", 12):
                    top = max(body[0], sp[0] - 4)
                    bot = X.content_bottom(gray, sc, c["x"][0], c["x"][1], top, limit, cfg["gap_stop"]) + cfg["bot_pad"]
                    item = {"num": prev["num"], "label": prev["label"], "page": pno + 1, "pdf_page": pno,
                            "column": names[ci], "bbox": [c["x"][0], round(top, 1), c["x"][1], round(min(bot, limit), 1)],
                            "continued": True}
                    if "num_end" in prev:
                        item["num_end"] = prev["num_end"]
                    out.append(item)
                    added.append((pno + 1, names[ci], prev["num"]))
            out.extend(mine)
            if mine:
                prev = mine[-1]
    return out, added


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf"); ap.add_argument("layout"); ap.add_argument("--out", required=True)
    ap.add_argument("--pages"); ap.add_argument("--no-sheets", action="store_true")
    ap.add_argument("--filter")
    ap.add_argument("--labels", action="store_true", help="print labels per page only")
    a = ap.parse_args()
    cfg = X.load_layout(a.layout)
    name = a.filter or cfg.get("label_filter")
    if name:
        FILTER = FILTERS[name]
    COLOR_MIN = cfg.get("label_color_min", COLOR_MIN)
    COLOR_DIFF = cfg.get("label_color_diff", COLOR_DIFF)
    only = parse_pages(a.pages) if a.pages else None
    problems, rep = X.extract(a.pdf, cfg, only, None)
    drops = {(d["page"], d["num"]) for d in cfg.get("drop_labels", [])}
    if drops:
        problems = [p for p in problems if (p["page"], p["num"]) not in drops]
        pl = X.page_list(cfg, fitz.open(a.pdf).page_count, only)
        rep.update(X.make_report(problems, pl, rep["pages_without_labels"]))
        rep["dropped"] = sorted(drops)
    if cfg.get("auto_continued"):
        problems, added = add_continued(a.pdf, cfg, problems, only)
        for pg_, col_, n_ in added:
            print(f"continued piece: page {pg_} col {col_} -> #{n_}")
        txt_extra = chr(10) + f"ℹ 이어지는 조각(continued) {len(added)}개: " + ", ".join(f"{a_}쪽{b_} #{c_}" for a_, b_, c_ in added)
    else:
        txt_extra = ""
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "problems.json"), "w", encoding="utf-8") as f:
        json.dump({"pdf": os.path.basename(a.pdf), "problems": problems}, f, ensure_ascii=False, indent=1)
    txt = X.report_text(rep) + txt_extra
    with open(os.path.join(a.out, "report.txt"), "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)
    if DROPPED:
        print("filter dropped:", len(DROPPED), DROPPED[:80])
    seq = {}
    for p in problems:
        seq.setdefault(p["page"], []).append(f'{p["column"]}{p["label"]}@{int(p["bbox"][1])}')
    for k, v in seq.items():
        print(k, " ".join(v))
    if not a.no_sheets:
        sheets = X.contact_sheets(a.pdf, problems, os.path.join(a.out, "sheets"))
        print(f"sheets {len(sheets)}: {os.path.join(a.out, 'sheets')}")
