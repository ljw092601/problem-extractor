# -*- coding: utf-8 -*-
# python fix_bbox.py <pdf> <extract 결과 problems.json> <slug 폴더> [--dry]
#   extract 결과를 고쳐 <slug 폴더>/problems.json 에 쓴다 (코드 수정 아님, core.extract 의 함수만 읽어 씀).
#   1) 기초 강화 문제 쪽(BASIC): 소문항 사이 여백이 커서 gap_stop 으로는 아래가 잘림 →
#      아랫변을 '다음 번호 / 다음 유형 제목 띠(01·02 …) 바로 위' 까지 큰 여백(BIG_GAP)으로 다시 잡고,
#      윗변이 바로 위 유형 제목 띠를 물면 띠 아래로 내림.
#   2) CONT: 단 맨 위에 번호 없이 이어지는 소문항 → continued 조각으로 추가.
#   3) 서술형 대비 문제의 '선택형' (N-1, N-2, N-3 중 하나 골라 풂) → '선택형' 띠부터 풀이 과정 도장까지 한 문제(num=N).
#      그 안에서 잡힌 번호 조각(N 이 여러 번)은 버림.
#   4) 번호 바로 위 '[ 주관식 ]' 표시를 윗변에 포함.
#   5) NO_MERGE: merge_continued 가 서로 다른 문제를 합치는 경우 num_end=num.
import sys, json, os, re
import fitz
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.extract import content_bottom, load_layout, columns_for

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
CONF = {
    "중3_개념유형_교사용부록_3-1": {"BASIC": (4, 17), "CONT": [(14, "R")], "NO_MERGE": []},
    # SET_CONT: 이미 잡힌 번호 항목을 continued 로 표시 (묶음 머리글만 앞 단에 있고 소문제가 다음 단에 있는 경우)
    "중3_개념유형_교사용부록_3-2": {"BASIC": (4, 19), "CONT": [], "NO_MERGE": [], "SET_CONT": [(64, "R", 4)]},
}
BIG_GAP = 200
CHOICE_GAP = 60

pdf, src, root = sys.argv[1], sys.argv[2], sys.argv[3]
conf = CONF[os.path.basename(os.path.normpath(root))]
BASIC, CONT, NO_MERGE = conf["BASIC"], conf["CONT"], conf["NO_MERGE"]
dry = "--dry" in sys.argv
cfg = load_layout(os.path.join(root, "layout.json"))
doc = fitz.open(pdf)
with open(src, encoding="utf-8") as f:
    d = json.load(f)
probs = d["problems"]
body = cfg["body"]
scale = 100 / 72


def spans(page):
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                yield s


def in_col(x, col, slack=4):
    return col["label_x"][0] - slack <= x <= col["label_x"][1] + slack


def type_headers(page, col):
    """유형 제목 띠 번호(11.9pt '01') → [(y0, y1)] (띠 전체 높이로 넓힘)"""
    out = []
    for s in spans(page):
        if 11 <= s["size"] <= 12.5 and re.match(r"^\d\d$", s["text"].strip()) and in_col(s["bbox"][0], col, 8):
            out.append((s["bbox"][1] - 5, s["bbox"][3] + 5))
    return out


def choice_blocks(page, col):
    """'선택형' 띠 → [(y0, N)]"""
    out = []
    ys = [s["bbox"][1] for s in spans(page) if s["text"].strip() == "선택형"
          and col["x"][0] - 5 <= s["bbox"][0] <= col["x"][0] + 40]
    for y in ys:
        n = None
        cands = []
        for s in spans(page):
            m = re.match(r"^(\d{1,2})\s*-?$", s["text"].strip())
            if m and 13 < s["size"] < 14.5 and y < s["bbox"][1] < y + 200 and in_col(s["bbox"][0], col, 6):
                cands.append((s["bbox"][1], int(m.group(1))))
        if cands:
            n = min(cands)[1]
        out.append((y, n))
    return out


def subj_marks(page, col):
    return [s["bbox"] for s in spans(page) if s["text"].strip() in ("주관식", "서술형")
            and col["x"][0] - 5 <= s["bbox"][0] <= col["x"][0] + 30]


def bars(page, col):
    """단 너비의 색 띠(1회/2회 머리 띠 등) → [(y0, y1)]"""
    out = []
    for dr in page.get_drawings():
        r = dr["rect"]
        if dr.get("fill") and r.width > 150 and r.height > 5 and r.x0 < col["x"][1] and r.x1 > col["x"][0]:
            out.append((r.y0, r.y1))
    return out


out = []
bypage = {}
for p in probs:
    bypage.setdefault(p["page"], []).append(p)
page_nums = []
for rng in cfg["pages"]:
    page_nums += list(range(rng[0], rng[1] + 1))
n_fix = n_cont = n_choice = n_subj = 0
for pg in page_nums:
    page = doc[pg - 1]
    cols = columns_for(cfg, pg - 1)
    gray = page.get_pixmap(dpi=100, colorspace=fitz.csGRAY)
    items = bypage.get(pg, [])
    basic = BASIC[0] <= pg <= BASIC[1]
    for ci, col in enumerate(cols):
        cname = "LR"[ci]
        its = sorted([p for p in items if p["column"] == cname], key=lambda p: p["bbox"][1])
        hdrs = type_headers(page, col) if basic else []
        # 3) 선택형 블록
        for cy, n in choice_blocks(page, col):
            top = cy - 4
            inside = [p for p in its if p["bbox"][1] > top - 2 and p["num"] == n]
            its = [p for p in its if p not in inside]
            nxt = [p["bbox"][1] for p in its if p["bbox"][1] > top]
            limit = (min(nxt) - 2) if nxt else body[1]
            cb = content_bottom(gray, scale, col["x"][0], col["x"][1], top, limit, CHOICE_GAP)
            q = {"num": n, "label": str(n), "page": pg, "pdf_page": pg - 1, "column": cname,
                 "bbox": [col["x"][0], round(top, 1), col["x"][1], round(min(limit, cb + cfg["bot_pad"]), 1)]}
            its.append(q)
            n_choice += 1
            print(f"선택형 {pg}{cname} num {n} (조각 {len(inside)}개 대체) bbox {q['bbox']}")
        its.sort(key=lambda p: p["bbox"][1])
        stops = sorted([p["bbox"][1] for p in its] + [h[0] for h in hdrs])
        # 2) 단 맨 위 넘어온 조각
        if (pg, cname) in CONT:
            y_start = body[0] + 4
            first = stops[0] if stops else body[1]
            cb = content_bottom(gray, scale, col["x"][0], col["x"][1], y_start, first - 2, BIG_GAP)
            prev = out[-1]
            piece = {"num": prev["num"], "label": prev["label"], "page": pg, "pdf_page": pg - 1,
                     "column": cname, "bbox": [col["x"][0], y_start, col["x"][1],
                                               round(min(first - 2, cb + cfg["bot_pad"]), 1)],
                     "continued": True}
            print(f"continued {pg}{cname} num {piece['num']} bbox {piece['bbox']}")
            out.append(piece)
            n_cont += 1
        cbars = bars(page, col)
        for p in its:
            y0 = p["bbox"][1]
            # 윗변이 색 띠 아랫부분을 물면 띠 아래로
            for b0, b1 in cbars:
                if b0 < y0 < b1 + 1.5 and b1 - y0 < 10:
                    p["bbox"][1] = y0 = round(b1 + 1.5, 1)
            # 4) [주관식]/[서술형] 표시
            for mb in subj_marks(page, col):
                if y0 - 25 < mb[1] < y0 + 4 and mb[3] < y0 + 16:
                    p["bbox"][1] = round(mb[1] - 3, 1)
                    n_subj += 1
            if basic:
                for h0, h1 in hdrs:
                    if h0 < y0 and h1 > y0:
                        p["bbox"][1] = round(h1 + 2, 1)
                nxt = [s for s in stops if s > y0 + 1]
                limit = (nxt[0] - 2) if nxt else body[1]
                cb = content_bottom(gray, scale, col["x"][0], col["x"][1], p["bbox"][1], limit, BIG_GAP)
                nb = round(min(limit, cb + cfg["bot_pad"]), 1)
                if abs(nb - p["bbox"][3]) > 0.5:
                    n_fix += 1
                p["bbox"][3] = nb
            # 6) 묶음: 마지막 소문제 번호가 아랫변 밖이면(소문제 사이 여백 > group_gap_stop) 거기까지 늘림
            if p.get("num_end", p["num"]) > p["num"]:
                lab = [s["bbox"] for s in spans(page) if 13 < s["size"] < 14.5
                       and s["text"].strip() == str(p["num_end"]) and in_col(s["bbox"][0], col)
                       and s["bbox"][1] > p["bbox"][1]]
                if lab and lab[0][1] > p["bbox"][3]:
                    nxt = [q["bbox"][1] for q in its if q["bbox"][1] > lab[0][1]]
                    limit = (min(nxt) - 2) if nxt else body[1]
                    cb = content_bottom(gray, scale, col["x"][0], col["x"][1], lab[0][1], limit, cfg["gap_stop"])
                    p["bbox"][3] = round(min(limit, cb + cfg["bot_pad"]), 1)
                    print(f"묶음 아래 늘림 {pg}{cname} {p['num']}~{p['num_end']} → {p['bbox'][3]}")
            if (p["page"], p["column"], p["num"]) in conf.get("SET_CONT", []):
                p["continued"] = True
                n_cont += 1
                print(f"continued(표시) {p['page']}{p['column']} num {p['num']}")
            if (p["page"], p["num"]) in NO_MERGE:
                p["num_end"] = p["num"]
            out.append(p)
print("bottom fixed", n_fix, "continued", n_cont, "선택형", n_choice, "주관식", n_subj, "items", len(out))
d["problems"] = out
if not dry:
    with open(os.path.join(root, "problems.json"), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
