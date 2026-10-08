# -*- coding: utf-8 -*-
# python fix_bbox.py <pdf> <extract 결과 problems.json> <slug 폴더> [--dry]
#   extract 결과를 복사하면서 (코드 수정 아님, core.extract 의 함수만 읽어 씀):
#   1) 기초 강화 문제 쪽(BASIC): 소문항 사이 여백이 커서 gap_stop 40 으로는 (2) 이하가 빠짐 →
#      아랫변을 '다음 번호 / 다음 유형 제목 띠(01·02 …) 바로 위' 까지 큰 여백(BIG_GAP)으로 다시 잡고,
#      윗변이 바로 위 유형 제목 띠를 물면 띠 아래로 내림.
#   2) 단 맨 위에 번호 없이 시작하는 내용(앞 단·쪽에서 넘어온 소문항) → continued 조각으로 추가.
#      (쪽 머리 큰 제목이 있는 쪽은 제목 아래(HDR_BOTTOM)부터 봄)
#   3) NO_MERGE: 번호가 코너마다 1부터 다시 시작해 merge_continued 가 서로 다른 문제를 합치는 경우 num_end=num.
import sys, json, os, re
import fitz
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from core.extract import content_bottom, load_layout, columns_for

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
BASIC = (20, 37)          # 기초 강화 문제 쪽
BIG_GAP = 200
HDR_BOTTOM = 88           # 쪽 머리 큰 제목(이름·점수 칸 / 기초 강화 문제 띠) 아래 y
NO_MERGE = [(32, 1)]      # 31쪽 오른쪽 조각(1번 이어짐) 바로 뒤 32쪽 1번은 다른 유형의 새 문제

pdf, src, root = sys.argv[1], sys.argv[2], sys.argv[3]
dry = "--dry" in sys.argv
cfg = load_layout(os.path.join(HERE, "layout.json"))
doc = fitz.open(pdf)
with open(src, encoding="utf-8") as f:
    d = json.load(f)
probs = d["problems"]
body = cfg["body"]
scale = 100 / 72
TP = cfg["top_pad"]


def type_headers(page, col):
    """유형 제목 띠 번호(14pt '01') → [(y0, y1)]"""
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                if 13 <= s["size"] <= 15 and re.match(r"^\d\d$", s["text"].strip()):
                    x = s["bbox"][0]
                    if col["label_x"][0] - 4 <= x <= col["label_x"][1] + 4:
                        out.append((s["bbox"][1], s["bbox"][3]))
    return out


def has_big_header(page):
    t = page.get_text()
    return ("이름" in t[:200]) or ("기초" in t[:20] and "강화" in t[:30])


out = []
pages = sorted({p["page"] for p in probs} | set(range(BASIC[0], BASIC[1] + 1)))
bypage = {}
for p in probs:
    bypage.setdefault(p["page"], []).append(p)
n_fix = n_cont = 0
page_nums = []
for rng in cfg["pages"]:
    page_nums += list(range(rng[0], rng[1] + 1))
last_num = None
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
        # 이벤트(다음 경계) = 번호 윗변(top_pad 뺀 값) + 제목 띠 윗변
        stops = sorted([p["bbox"][1] for p in its] + [h[0] - 6 for h in hdrs])
        # 2) 단 맨 위 넘어온 조각
        y_start = HDR_BOTTOM if has_big_header(page) else body[0]
        first = stops[0] if stops else body[1]
        if first - y_start > 20 and last_num is not None:
            cb = content_bottom(gray, scale, col["x"][0], col["x"][1], y_start, first - 2, BIG_GAP)
            if cb > y_start + 5:
                # 내용 윗끝
                top = None
                px0, px1 = int(col["x"][0] * scale), int(col["x"][1] * scale)
                for ry in range(int(y_start * scale), int(first * scale)):
                    row = gray.samples[ry * gray.stride + px0: ry * gray.stride + px1]
                    if min(row, default=255) < 150:
                        top = ry / scale
                        break
                piece = {"num": last_num, "label": str(last_num), "page": pg, "pdf_page": pg - 1,
                         "column": cname, "bbox": [col["x"][0], round(max(y_start, top - 6), 1), col["x"][1],
                                                   round(min(first - 2, cb + cfg["bot_pad"]), 1)],
                         "continued": True}
                print(f"continued {pg}{cname} num {last_num} bbox {piece['bbox']}")
                out.append(piece)
                n_cont += 1
        for p in its:
            if basic:
                y0 = p["bbox"][1]
                # 윗변이 바로 위 제목 띠를 물면 띠 아래로
                for h0, h1 in hdrs:
                    if h0 < y0 + TP and h1 + 3 > y0:
                        p["bbox"][1] = round(h1 + 3, 1)
                nxt = [s for s in stops if s > y0 + 1]
                limit = (nxt[0] - 2) if nxt else body[1]
                cb = content_bottom(gray, scale, col["x"][0], col["x"][1], p["bbox"][1], limit, BIG_GAP)
                nb = round(min(limit, cb + cfg["bot_pad"]), 1)
                if abs(nb - p["bbox"][3]) > 0.5:
                    n_fix += 1
                p["bbox"][3] = nb
            if (p["page"], p["num"]) in NO_MERGE:
                p["num_end"] = p["num"]
            out.append(p)
            last_num = p["num"]
print("bottom fixed", n_fix, "continued", n_cont, "problems", len(out))
d["problems"] = out
if not dry:
    with open(os.path.join(root, "problems.json"), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
