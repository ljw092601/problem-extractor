# -*- coding: utf-8 -*-
"""book_tool.py 실행 래퍼 (마플 시너지 내신연계문제 전용). core 코드는 고치지 않고 런타임에만 덮어씀.
1) 문제 번호 글자 순서가 PDF 글자 정보에 뒤집혀 저장됨('681' = 186번) → 20pt 숫자 조각을 뒤집는다.
   (단, 4자리 '0732' 같은 오타 번호는 뒤집으면 규칙에 안 맞아 빠짐 → layout 의 manual_labels 로 넣음)
2) 소단원 첫 쪽은 번호 글꼴 인코딩이 깨져 있음('770','333' 등) → layout 의 "renumber_pages" 쪽은
   위치(단·y)는 그대로 쓰고 번호만 앞 쪽 마지막 번호+1 부터 차례로 다시 매긴다 (첫 쪽이면 다음 쪽 첫 번호에서 역산).
사용: python bt_rev.py extract <pdf> <layout.json> --out D   (book_tool.py 와 같은 인자)"""
import json
import os
import re
import sys

ROOT = r"C:\Users\ljw09\Desktop\promblem_area"
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from core import extract as X  # noqa: E402

_orig_tokens = X._text_tokens


def _rev_tokens(page):
    for text, bbox, size in _orig_tokens(page):
        if size >= 18 and re.fullmatch(r"\d{2,4}", text):
            text = text[::-1]
        yield text, bbox, size


X._text_tokens = _rev_tokens

RENUMBER, BOTTOM_FIX = [], []
if len(sys.argv) >= 4 and sys.argv[1] == "extract":
    with open(sys.argv[3], encoding="utf-8") as f:
        _lay = json.load(f)
    RENUMBER = sorted(_lay.get("renumber_pages", []))
    BOTTOM_FIX = _lay.get("bottom_fix", [])   # [{"page": 21, "num": 105, "y1": 797}] 본문 아래 경계(body)를 넘는 문제 하나만 아래 끝 지정

_orig_drop = X.drop_outliers


def _renumber_then_drop(problems, *a, **k):
    for pg in RENUMBER:
        idx = [i for i, p in enumerate(problems) if p["page"] == pg]
        if not idx:
            continue
        before = [p for p in problems[:idx[0]]]
        after = problems[idx[-1] + 1:]
        if before:
            start = before[-1].get("num_end", before[-1]["num"]) + 1
        elif after:
            start = after[0]["num"] - len(idx)
        else:
            continue
        for n, i in enumerate(idx):
            problems[i]["num"] = start + n
            problems[i]["label"] = f"{start + n:03d}#"
    for fx in BOTTOM_FIX:
        for p in problems:
            if p["page"] == fx["page"] and p["num"] == fx["num"]:
                p["bbox"][3] = fx["y1"]
    return _orig_drop(problems, *a, **k)


X.drop_outliers = _renumber_then_drop

import book_tool  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
book_tool.main()
