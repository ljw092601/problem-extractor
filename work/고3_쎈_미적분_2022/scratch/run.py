# -*- coding: utf-8 -*-
"""쪽마다 스캔이 좌우로 밀려(가운데 구분선 x 가 홀수 쪽 287~295, 짝수 쪽 305~310) 고정 columns 로는
흐린 구분선을 물어(→ 문제 아래 여백을 못 찾고 다음 제목 띠까지 딸려 옴) 쪽별 구분선 위치(div.json)로 columns 를 계산한다.
core 는 고치지 않고 X.columns_for 만 바꿔 끼운다 (고2_쎈_미적분2 와 같은 방식).
    python work/<slug>/scratch/run.py extract <pdf> <layout.json> --out D [--pages ..] [--no-sheets]
환경변수 없이 이 파일 옆 div.json / geom.json 을 쓴다.
geom.json: {"odd": [lo, hi], "even": [lo, hi], "lx": [a, b], "rx0": r, "rend_odd": e1, "rend_even": e2, "rlx": [a, b]}"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from core import extract as X  # noqa: E402

G = json.load(open(os.path.join(HERE, "geom.json"), encoding="utf-8"))
raw = json.load(open(os.path.join(HERE, "div.json")))
DIV = {}
for k, v in raw.items():
    p, c = int(k), v[0]
    lo, hi = G["odd"] if p % 2 else G["even"]
    if c is not None and lo <= c <= hi:
        DIV[p] = c
_pages = [int(k) for k in raw]
for p in range(min(_pages), max(_pages) + 1):          # 못 잰 쪽: 같은 홀짝 가까운 쪽 2개 평균
    if p not in DIV:
        near = sorted((q for q in DIV if q % 2 == p % 2), key=lambda q: abs(q - p))[:2]
        DIV[p] = round(sum(DIV[q] for q in near) / len(near), 1)


def cols_for_div(c, odd):
    lx, rlx = G["lx"], G["rlx"]
    return [{"x": [round(c - G["lx0"], 1), round(c - 4, 1)], "label_x": [round(c - lx[0], 1), round(c - lx[1], 1)]},
            {"x": [round(c + G["rx0"], 1), round(c + (G["rend_odd"] if odd else G["rend_even"]), 1)],
             "label_x": [round(c + rlx[0], 1), round(c + rlx[1], 1)]}]


def columns_for(cfg, pno):
    p = pno + 1
    odd = p % 2 == 1
    c = DIV.get(p)
    if c is None:
        return X._orig_columns_for(cfg, pno)
    return cols_for_div(c, odd)


# 번호로 잘못 읽힌 본문 숫자 (쪽, 번호) — layout.json 의 "ignore_labels". 앞 문제가 여기서 잘리는 것을 막는다.
if not hasattr(X, "_orig_page_labels"):
    X._orig_page_labels = X.page_labels


def page_labels(page, cfg, pno=None, *a, **k):
    labels = X._orig_page_labels(page, cfg, pno, *a, **k)
    bad = {(p, n) for p, n in cfg.get("ignore_labels", [])}
    return [d for d in labels if (pno + 1, d["num"]) not in bad]


X.page_labels = page_labels

if not hasattr(X, "_orig_columns_for"):
    X._orig_columns_for = X.columns_for
X.columns_for = columns_for

if __name__ == "__main__":
    import book_tool  # noqa: E402
    if sys.argv[1:2] == ["dump"]:
        print(json.dumps(DIV))
    else:
        sys.argv = ["book_tool.py"] + sys.argv[1:]
        book_tool.main()
