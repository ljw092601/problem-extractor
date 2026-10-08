# -*- coding: utf-8 -*-
"""book_tool.py 를 그대로 부르되, OCR 번호 후보에 '최소 글자 높이' 거르기를 더하는 임시 우회 (core 코드는 건드리지 않음).
layout.json 의 "label_min_h" (pt) 보다 낮은 OCR 조각은 번호로 보지 않는다.
(마플시너지: 문제 번호는 높이 14~16pt, 보기 '①12' 가 '012' 로 읽힌 조각은 6~10pt)
사용: python work/마플시너지_공통수학2/extract_minh.py extract <pdf> <layout.json> --out D [--pages ..] [--no-sheets]
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from core import extract as X  # noqa: E402
import book_tool  # noqa: E402

_orig = X._match_labels


def _match_labels(toks, cfg, cols, body, slack=0):
    mh = cfg.get("label_min_h")
    if mh and cfg.get("source") == "ocr":
        toks = [t for t in toks if t[2] >= mh]
    return _orig(toks, cfg, cols, body, slack)


X._match_labels = _match_labels

if __name__ == "__main__":
    book_tool.main()
