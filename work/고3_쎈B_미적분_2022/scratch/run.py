# -*- coding: utf-8 -*-
"""layout.json 의 "ignore_labels"(번호로 잘못 읽힌 본문 숫자)를 빼고 추출한다. columns 는 layout.json 그대로.
    python work/<slug>/scratch/run.py extract <pdf> <layout.json> --out D [--pages ..] [--no-sheets]
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from core import extract as X  # noqa: E402

# 번호로 잘못 읽힌 본문 숫자 (쪽, 번호) — layout.json 의 "ignore_labels". 앞 문제가 여기서 잘리는 것을 막는다.
if not hasattr(X, "_orig_page_labels"):
    X._orig_page_labels = X.page_labels


def page_labels(page, cfg, pno=None, *a, **k):
    labels = X._orig_page_labels(page, cfg, pno, *a, **k)
    bad = {(p, n) for p, n in cfg.get("ignore_labels", [])}
    return [d for d in labels if (pno + 1, d["num"]) not in bad]


X.page_labels = page_labels

if __name__ == "__main__":
    import book_tool  # noqa: E402
    if True:
        sys.argv = ["book_tool.py"] + sys.argv[1:]
        book_tool.main()
