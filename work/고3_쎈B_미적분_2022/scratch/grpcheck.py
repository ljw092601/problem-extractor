# -*- coding: utf-8 -*-
"""ocrtext 전체 출력에서 묶음 머리글 '[a~b]' 를 찾아, problems.json 에서 묶음으로 안 잡힌 것을 manual_groups 후보로 출력.
    python grpcheck.py <ocrtext 출력.txt> <problems.json> [digits]
출력 JSON 줄: {"page", "col", "y", "range"} (col 은 a 번 문제(개별 조각)가 있는 단, y = OCR 줄 top)"""
import json, re, sys
txt, pj = sys.argv[1:3]
DIG = int(sys.argv[3]) if len(sys.argv) > 3 else 4
P = json.load(open(pj, encoding="utf-8"))["problems"]
grp = {(p["page"], p["num"]) for p in P if p.get("num_end")}
single = {}
for p in P:
    if not p.get("num_end"):
        single.setdefault(p["num"], p)
rx = re.compile(r"\[\s*(\d{%d})\s*[~\-—–]\s*([0-9기ㄱlIO]{%d,})" % (DIG, DIG))
page = None
out = []
for line in open(txt, encoding="utf-8-sig", errors="replace"):
    m = re.match(r"---\s*(\d+)쪽", line)
    if m:
        page = int(m.group(1))
        continue
    m = re.match(r"\s*y\s+(\d+)\s+x\s+(\d+):\s*(.*)", line)
    if not m:
        continue
    y = int(m.group(1))
    for g in rx.finditer(m.group(3)):
        a = int(g.group(1))
        bs = g.group(2).replace("기", "7").replace("ㄱ", "7").replace("l", "1").replace("I", "1").replace("O", "0")[:DIG]
        try:
            b = int(bs)
        except ValueError:
            continue
        if not (a < b <= a + 30):
            b = None
        if (page, a) in grp:
            continue
        s = single.get(a)
        if s is None or s["page"] != page:
            print("?? 개별 조각 없음", page, a, b, "|", m.group(3)[:60])
            continue
        col = 0 if s["column"] == "L" else 1
        if b is None:                                      # 같은 단에서 이어지는 개별 번호로 끝 추정
            b = a
            while (b + 1) in single and single[b + 1]["page"] == page and single[b + 1]["column"] == s["column"]:
                b += 1
            print("?? 끝 번호 추정", page, a, b, "|", m.group(3)[:60])
        out.append({"page": page, "col": col, "y": y, "range": [a, b]})
for o in out:
    print(json.dumps(o))
