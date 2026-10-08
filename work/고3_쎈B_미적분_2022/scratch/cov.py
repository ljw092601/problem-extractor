# -*- coding: utf-8 -*-
"""problems.json 번호 점검: 빠진 번호, 중복, 묶음 목록.  python cov.py <problems.json>"""
import json, sys
P = json.load(open(sys.argv[1], encoding="utf-8"))["problems"]
cov = {}
for p in P:
    for n in range(p["num"], p.get("num_end", p["num"]) + 1):
        cov.setdefault(n, []).append(p["page"])
lo, hi = min(cov), max(cov)
miss = [n for n in range(lo, hi + 1) if n not in cov]
print("범위", lo, hi, "빠진 번호", len(miss), miss[:200])
seen = {}
for p in P:
    if not p.get("continued"):
        seen.setdefault(p["num"], []).append(p["page"])
print("중복:", {n: v for n, v in seen.items() if len(v) > 1})
print("묶음:", [(p["page"], p["label"]) for p in P if p.get("num_end") and not p.get("continued")])
print("항목", len(P), "문제", sum(1 for p in P if not p.get("continued")),
      "이어짐", sum(1 for p in P if p.get("continued")))
