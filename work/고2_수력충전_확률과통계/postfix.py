# -*- coding: utf-8 -*-
"""고2_수력충전_확률과통계 후처리 (core 코드는 건드리지 않음).

    python postfix.py <main problems.json> <p187 problems.json> <color72 폴더> <출력 problems.json>

- 원본 PDF 는 MuPDF 로 그리면 글자 일부가 빠지는 쪽이 많아서, 추출은 poppler 로 다시 그린 사본으로 했다
  (쪽 크기·좌표 동일). color72 = `pdftoppm -cropbox -r 72 -png 원본 <폴더>/p` 결과 (1px = 1pt).
- 187쪽은 cropbox 가 달라(재단선 포함 판) 따로 layout_p187.json 으로 추출한 결과로 바꿔 끼운다.
1) 튀는 번호(보기 ①·분수를 번호로 읽은 것) 삭제 → 바로 위 같은 단 문제를 그 아래까지 늘림
   같은 단에서 묶음 범위 안 번호가 뒤에 따로 잡히면 묶음에 흡수
2) 문제 아래로 다음 '유형 NN' 제목 띠(분홍 태그)가 딸려 오면 띠 위에서 자름
3) 문제 맨 아래에 붙은 주황 테두리 팁 말풍선을 잘라 냄 (말풍선 아래에 내용이 더 없을 때만)
"""
import json
import os
import sys

from PIL import Image

main_p, p187_p, c72, out_p = sys.argv[1:5]
probs = json.load(open(main_p, encoding="utf-8"))["problems"]
p187 = json.load(open(p187_p, encoding="utf-8"))["problems"]
probs = [p for p in probs if p["page"] < 187] + p187 + [p for p in probs if p["page"] > 187]

log = []

# 0) 개별 수정: OCR 이 잘못 읽은 번호·묶음 범위
for p in probs:
    if p["page"] == 116 and p["column"] == "L" and p["num"] == 2 and p["bbox"][1] < 220:
        p["num"], p["label"], p["bbox"][1] = 1, "01*", 118.0       # 01 번호를 못 읽고 분수 '2' 를 번호로 읽음
        log.append("수정 116L 2(y198) → 01")
    if p["page"] == 184 and p["column"] == "L" and p["num"] == 1 and p.get("num_end") == 5:
        p["num_end"], p["label"] = 3, "01~03"                      # [01-03] 을 [01-05] 로 읽음
        log.append("수정 184L 묶음 01~05 → 01~03")


def same_col(a, b):
    return a["page"] == b["page"] and a["column"] == b["column"]


# ---------------------------------------------------------------- 1) 튀는 번호
kept = []
for i, p in enumerate(probs):
    nxt = probs[i + 1] if i + 1 < len(probs) else None
    if p.get("num_end"):
        kept.append(p)
        continue
    last = kept[-1] if kept else None
    # 가장 최근 묶음(바로 앞이 묶음이거나 그 묶음의 이어진 조각)
    g = last if last and last.get("num_end") else (last.get("_grp") if last else None)
    if g and g["num"] <= p["num"] <= g["num_end"]:
        if same_col(last, p) and p["bbox"][1] > last["bbox"][1]:
            last["bbox"][3] = max(last["bbox"][3], p["bbox"][3])
            log.append(f"흡수 {p['page']}{p['column']} {p['num']} → 앞 조각 (묶음 {g['num']}~{g['num_end']})")
            continue
        p["_grp"] = g
        kept.append(p)
        continue
    last_num = (last.get("num_end") or (last["_grp"]["num_end"] if last.get("_grp") else last["num"])) if last else 0
    nnum = nxt["num"] if nxt else None
    ok = p["num"] == last_num + 1 or (p["num"] == 1 and not (nnum == last_num + 1 and last_num > 1)) \
        or (nnum is not None and nnum == p["num"] + 1)
    if ok and nxt and not nxt.get("num_end") and nnum == p["num"] and same_col(p, nxt) and p["num"] == last_num + 1:
        # 같은 번호가 바로 또 나오면 작은(앞) 것이 분수 조각 → 뒤의 것을 씀
        ok = False
    if ok:
        kept.append(p)
        continue
    if last and same_col(last, p) and last["bbox"][1] < p["bbox"][1]:
        last["bbox"][3] = max(last["bbox"][3], p["bbox"][3])
    log.append(f"삭제(튀는 번호) {p['page']}{p['column']} {p['num']} y{p['bbox'][1]:.0f}")
probs = kept
for p in probs:
    if p.pop("_grp", None) is not None:
        p["continued"] = True                 # 묶음이 다음 단·쪽으로 넘어간 조각 → 등록 때 앞 묶음에 이어 붙음

# ---------------------------------------------------------------- 2)·3) 이미지로 다듬기
_cache = {}
KEEP_ART = {(34, "L", 10)}   # 문제 그림(전구)이 주황색이라 말풍선으로 오인되는 곳


def img(page):
    if page not in _cache:
        _cache.clear()
        _cache[page] = Image.open(os.path.join(c72, f"p-{page:03d}.png")).convert("RGB")
    return _cache[page]


def is_pink(px):
    r, g, b = px
    return r > 190 and b > 125 and r - g > 60


def is_orange(px):
    r, g, b = px
    return r > 200 and 60 <= g <= 215 and b < 200 and r - b > 40


def is_dark(px):
    return min(px) < 150


def row_count(im, y, x0, x1, f):
    y = int(y)
    if y < 0 or y >= im.height:
        return 0
    return sum(1 for x in range(int(x0), min(int(x1), im.width)) if f(im.getpixel((x, y))))


for i, p in enumerate(probs):
    im = img(p["page"])
    x0, y0, x1, y1 = p["bbox"]
    nxt = probs[i + 1] if i + 1 < len(probs) else None
    # 2) 제목 띠: 분홍 태그 가로줄(30px 이상)이 단 왼쪽 90pt 안에
    if nxt and same_col(p, nxt):
        lo = max(y0 + 25, nxt["bbox"][1] - 70)
        for y in range(int(lo), int(y1) + 1):
            if row_count(im, y, x0, x0 + 90, is_pink) >= 30:
                p["bbox"][3] = y - 4
                log.append(f"제목 띠 자름 {p['page']}{p['column']} {p['num']}: {y1:.0f}→{y - 4}")
                break
    x0, y0, x1, y1 = p["bbox"]
    # 3) 팁 말풍선: 영역 맨 아래 덩어리(빈 줄 3pt 이상으로 떨어진)에 주황 테두리가 많으면 그 덩어리를 뺌
    ink = [row_count(im, y, x0 + 6, x1 - 14, lambda px: min(px) < 225) > 0 for y in range(int(y0), int(y1) + 1)]
    blocks, start, blank = [], None, 0
    for k, v in enumerate(ink):
        if v:
            if start is None or blank >= 3:
                if start is not None:
                    blocks.append((start, last_ink))
                start = k
            last_ink, blank = k, 0
        else:
            blank += 1
    if start is not None:
        blocks.append((start, last_ink))
    if len(blocks) >= 2:
        bt, bb = blocks[-1]
        top, bot = int(y0) + bt, int(y0) + bb
        orange = sum(row_count(im, y, x0, x1, is_orange) for y in range(top, bot + 1))
        border = max(row_count(im, y, x0, x1, is_orange) for y in range(top, bot + 1))   # 가로 테두리
        if orange >= 60 and border >= 25 and top > y0 + 30 and (p["page"], p["column"], p["num"]) not in KEEP_ART:
            prev_bot = int(y0) + blocks[-2][1]
            cut = min(top - 2, prev_bot + 6)
            p["bbox"][3] = cut
            log.append(f"말풍선 자름 {p['page']}{p['column']} {p['num']}: {y1:.0f}→{cut}")

json.dump({"pdf": "22개정 수력충전 확률과통계 본책(학셍용).pdf", "problems": probs},
          open(out_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(probs), "문제")
print("\n".join(log))
