# -*- coding: utf-8 -*-
"""쪽마다 스캔이 좌우로 밀려(가운데 구분선 x 가 홀수 275~286, 짝수 293~310) 고정 columns 로는
구분선을 물거나 글자를 자른다. core 를 고치지 않고, 쪽별 구분선 위치(div.json)로 columns 를 계산해 넣는다.
    python work/고2_쎈_미적분2/scratch/run.py extract <pdf> <layout.json> --out D [--pages ..] [--no-sheets]
(book_tool.py 와 같은 인자. X.columns_for 만 바꿔 끼운다)"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from core import extract as X  # noqa: E402
import book_tool  # noqa: E402

raw = json.load(open(os.path.join(HERE, "div.json")))
DIV = {}
for k, (meas, _strength, ink) in raw.items():
    p = int(k)
    odd = p % 2 == 1
    ink_ok = (20 <= ink <= 40) if odd else (40 <= ink <= 62)
    meas_ok = meas is not None and ((272 <= meas <= 290) if odd else (290 <= meas <= 312))
    est = ink + 251 if ink_ok else None
    if meas_ok and (est is None or abs(meas - est) <= 4):
        DIV[p] = meas
    elif est is not None:
        DIV[p] = est
for p in range(9, 192):                       # 못 잰 쪽: 같은 홀짝 가까운 쪽 값
    if p not in DIV:
        near = sorted((q for q in DIV if q % 2 == p % 2), key=lambda q: abs(q - p))[:2]
        DIV[p] = round(sum(DIV[q] for q in near) / len(near))


def cols_for_div(c, odd):
    # 홀수 쪽은 오른쪽 끝에 단원 색띠(c+282~)가 있어 오른쪽 단을 c+271 까지만
    return [{"x": [c - 262, c - 4], "label_x": [c - 258, c - 234]},
            {"x": [c + 4, c + (271 if odd else 275)], "label_x": [c + 8, c + 32]}]


def columns_for(cfg, pno):
    odd = (pno + 1) % 2 == 1
    return cols_for_div(DIV.get(pno + 1, 283 if odd else 303), odd)


X.columns_for = columns_for

# 번호로 잘못 읽힌 본문 숫자 (쪽, 번호) — layout.json 의 "ignore_labels". 앞 문제가 여기서 잘리는 것을 막는다.
_orig_page_labels = X.page_labels


def page_labels(page, cfg, pno=None, *a, **k):
    labels = _orig_page_labels(page, cfg, pno, *a, **k)
    bad = {(p, n) for p, n in cfg.get("ignore_labels", [])}
    return [d for d in labels if (pno + 1, d["num"]) not in bad]


X.page_labels = page_labels

if __name__ == "__main__":
    if sys.argv[1:2] == ["dump"]:
        print(json.dumps(DIV))
    else:
        sys.argv = ["book_tool.py"] + sys.argv[1:]
        book_tool.main()
