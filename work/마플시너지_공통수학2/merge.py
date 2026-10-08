# -*- coding: utf-8 -*-
"""구간별 extract 결과(problems.json)들을 읽는 순서(쪽 → 왼쪽 단 → 오른쪽 단 → 위→아래)로 합친다.
사용: python merge.py out/problems.json a/problems.json b/problems.json ...
같은 (쪽, 단, 위 y) 가 겹치면 먼저 준 파일 것을 쓴다."""
import json
import sys

out, srcs = sys.argv[1], sys.argv[2:]
pdf, allp, seen = None, [], set()
for s in srcs:
    d = json.load(open(s, encoding="utf-8"))
    pdf = pdf or d.get("pdf")
    for p in d["problems"]:
        k = (p["page"], p["column"], round(p["bbox"][1]))
        if k in seen:
            continue
        seen.add(k)
        allp.append(p)
allp.sort(key=lambda p: (p["page"], 1 if p["column"] == "R" else 0, p["bbox"][1]))
with open(out, "w", encoding="utf-8") as f:
    json.dump({"pdf": pdf, "problems": allp}, f, ensure_ascii=False, indent=1)
print(len(allp), "문제 ->", out)
