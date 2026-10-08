# -*- coding: utf-8 -*-
"""layout_A / layout_A2 / layout_B 로 따로 뽑은 결과(각 폴더의 problems.json)를 쪽 → 단 → y 순으로 합쳐
이 폴더의 problems.json, report.txt 로. (저장소 코드는 안 고침)
usage: python merge.py <A 결과 폴더> <A2 결과 폴더> <B 결과 폴더>"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
allp = []
reps = []
for d in sys.argv[1:]:
    allp += json.load(open(os.path.join(d, "problems.json"), encoding="utf-8"))["problems"]
    reps.append(f"== {os.path.basename(d.rstrip('/\\\\'))}\n" + open(os.path.join(d, "report.txt"), encoding="utf-8").read())
order = {"L": 0, "0": 0, "R": 1}
allp.sort(key=lambda p: (p["page"], order.get(p["column"], 0), p["bbox"][1]))
for p in allp:
    if p["column"] == "0":
        p["column"] = "L"      # 1단 쪽(도전 문제)은 L 로
json.dump({"pdf": "비상 자습서 평가문제집 중3 문제.pdf", "problems": allp},
          open(os.path.join(HERE, "problems.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(HERE, "report.txt"), "w", encoding="utf-8").write(
    f"합계 {len(allp)}개 (묶음 {sum(1 for p in allp if 'num_end' in p)}개)\n\n" + "\n".join(reps))
print(len(allp))
