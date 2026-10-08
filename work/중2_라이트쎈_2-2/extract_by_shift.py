"""(참고용 스크립트 — 작업 당시 scratch 에서 실행. sv<book>.json = 쪽 전체 OCR 조사 결과(번호 x 위치), base_<book>.json = layouts/base_settings.json)
per-page-shift binned extraction.
usage: drive.py <book: 21|22> <outdir> [pages e.g. 8-20,30] [--sheets]
reads base settings from base_<book>.json and per-page shift from sv<book>.json
"""
import sys, os, json, re
sys.path.insert(0, r"C:\Users\ljw09\Desktop\promblem_area")
import fitz
from core import extract as X

HERE = os.path.dirname(os.path.abspath(__file__))
import pickle, hashlib
_orig_ocr = X._ocr_page
CACHE = os.path.join(HERE, "ocrcache")
os.makedirs(CACHE, exist_ok=True)


def _cached_ocr(page, cfg):
    key = f"{os.path.basename(page.parent.name)}|{page.number}|{cfg['ocr_dpi']}|{cfg.get('body')}"
    fn = os.path.join(CACHE, hashlib.md5(key.encode()).hexdigest() + ".pkl")
    if os.path.exists(fn):
        return pickle.load(open(fn, "rb"))
    r = _orig_ocr(page, cfg)
    pickle.dump(r, open(fn, "wb"))
    return r


X._ocr_page = _cached_ocr
_orig_rescue = X._rescue_tokens


def _cached_rescue(page, cfg, cols, body):
    key = f"R|{os.path.basename(page.parent.name)}|{page.number}|{[c['label_x'] for c in cols]}|{body}"
    fn = os.path.join(CACHE, hashlib.md5(key.encode()).hexdigest() + ".pkl")
    if os.path.exists(fn):
        return pickle.load(open(fn, "rb"))
    r = _orig_rescue(page, cfg, cols, body)
    pickle.dump(r, open(fn, "wb"))
    return r


X._rescue_tokens = _cached_rescue
sys.stdout.reconfigure(encoding="utf-8")
book, out = sys.argv[1], sys.argv[2]
only = None
if len(sys.argv) > 3 and not sys.argv[3].startswith("--"):
    only = set()
    for part in sys.argv[3].split(","):
        if "-" in part:
            a, b = part.split("-"); only.update(range(int(a), int(b) + 1))
        else:
            only.add(int(part))
sheets = "--sheets" in sys.argv
base = json.load(open(os.path.join(HERE, f"base_{book}.json"), encoding="utf-8"))
pdf = base.pop("pdf")
sv = json.load(open(os.path.join(HERE, f"sv{book}.json"), encoding="utf-8"))
rx = re.compile(r"^\[?(\d{4})\]?$")


def shift(p):
    if str(p) in base.get("shift_override", {}):
        return base["shift_override"][str(p)]
    v = sv[str(p)]
    L, R = [], []
    for t, b in v["toks"]:
        if not rx.match(t) or b[3] - b[1] < 9:
            continue
        if b[0] < 120: L.append(b[0])
        elif 260 < b[0] < 380: R.append(b[0])
    def mode(xs):
        if not xs: return None
        return max(sorted(xs), key=lambda x: (sum(abs(y - x) < 4 for y in xs), -x))
    l, r = mode(L), mode(R)
    if l and r and 261 <= r - l <= 270:
        return (l + r - 266) / 2
    if l and l < 80:
        return l
    if r:
        return r - 266
    return None


BW = 6
pages_all = []
for a, b in base["pages"]:
    pages_all += list(range(a, b + 1))
pages_all = [p for p in pages_all if p not in set(base.get("skip_pages", []))]
if only:
    pages_all = [p for p in pages_all if p in only]
bins = {}
for p in pages_all:
    s = shift(p)
    if s is None:
        s = base.get("default_shift", 35)
    k = round((s - 20) / BW)
    bins.setdefault(k, []).append(p)

os.makedirs(out, exist_ok=True)
os.makedirs(os.path.join(out, "layouts"), exist_ok=True)
problems, empty = [], []
tmpl = base["cfg"]
for k in sorted(bins):
    c = 20 + k * BW
    cfg = json.loads(json.dumps(tmpl))
    cfg["columns"] = [{"x": [round(c - 12, 1), round(c + 252, 1)], "label_x": [round(c - 6, 1), round(c + 9, 1)]},
                      {"x": [round(c + 257, 1), round(c + 526, 1)], "label_x": [round(c + 257, 1), round(c + 276, 1)]}]
    cfg["pages"] = [[p, p] for p in bins[k]]
    cfg["drop_outliers"] = False
    ml = [m for m in tmpl.get("manual_labels", []) if m["page"] in bins[k]]
    mg = [m for m in tmpl.get("manual_groups", []) if m["page"] in bins[k]]
    cfg["manual_labels"], cfg["manual_groups"] = ml, mg
    with open(os.path.join(out, "layouts", f"layout_shift{c}.json"), "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)
    cfg = X.load_layout(os.path.join(out, "layouts", f"layout_shift{c}.json"))
    pr, rep = X.extract(pdf, cfg)
    problems += pr
    empty += rep.get("pages_without_labels", [])
    print("bin", c, len(bins[k]), "pages ->", len(pr), flush=True)

problems.sort(key=lambda d: (d["page"], d["column"], d["bbox"][1]))
# group spilling into next column/page: single labels inside previous group's range at top of next column
merged, auto_cont = [], []
for d in problems:
    if merged and "num_end" not in d:
        prev = merged[-1]
        g = prev if "num_end" in prev else None
        if prev.get("continued") and "num_end" in prev:
            g = prev
        if g and g["num"] < d["num"] <= g["num_end"]:
            same_place = (prev["page"], prev["column"]) == (d["page"], d["column"])
            if prev.get("continued") and same_place:
                prev["bbox"][3] = max(prev["bbox"][3], d["bbox"][3])     # extend fragment
                prev["label"] = prev["label"].split("~")[0] + "~" + d["label"]
                continue
            if not same_place:
                frag = {**d, "num": g["num"], "num_end": g["num_end"], "continued": True,
                        "bbox": list(d["bbox"]), "label": d["label"]}
                merged.append(frag)
                auto_cont.append((d["page"], d["column"], g["num"], d["num"]))
                continue
    merged.append(d)
problems = merged
print("auto continued:", auto_cont)
# continued marks (manual)
for c in tmpl.get("continued", []):
    for d in problems:
        if d["page"] == c["page"] and d["num"] == c["num"]:
            d["continued"] = True
main = [d for d in problems if not d.get("continued")]
if tmpl.get("drop_outliers", True):
    main2, dropped = X.drop_outliers(main)
    keep = {id(d) for d in main2}
    problems = [d for d in problems if d.get("continued") or id(d) in keep]
    main = main2
else:
    dropped = []
rep = X.make_report(main, sorted(pages_all), sorted(empty))
rep["n_continued"] = sum(1 for d in problems if d.get("continued"))
rep["dropped"] = dropped
rep["offband_pages"] = []
rep["rescued"] = 0
rep["groups"] = sum(1 for d in problems if "num_end" in d)
with open(os.path.join(out, "problems.json"), "w", encoding="utf-8") as f:
    json.dump({"pdf": os.path.basename(pdf), "problems": problems}, f, ensure_ascii=False, indent=1)
txt = X.report_text(rep)
with open(os.path.join(out, "report.txt"), "w", encoding="utf-8") as f:
    f.write(txt)
print(txt)
if sheets:
    X.contact_sheets(pdf, problems, os.path.join(out, "sheets"))
