# -*- coding: utf-8 -*-
"""run_A(배운대로 복습하기) + run_B(서술형 훈련하기) 결과를 합쳐 problems.json / report.txt 로. usage: python merge.py"""
import json, os
H = os.path.dirname(os.path.abspath(__file__))
allp = []
rep = ""
for d in ("run_A", "run_B"):
    allp += json.load(open(os.path.join(H, d, "problems.json"), encoding="utf-8"))["problems"]
    rep += f"== {d}\n" + open(os.path.join(H, d, "report.txt"), encoding="utf-8").read()
allp.sort(key=lambda p: (p["page"], 0 if p["column"] == "L" else 1, p["bbox"][1]))
json.dump({"pdf": "2021 수학의바이블 중등 3-2 워크북.pdf", "problems": allp},
          open(os.path.join(H, "problems.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(os.path.join(H, "report.txt"), "w", encoding="utf-8").write(f"합계 {len(allp)}개\n\n" + rep)
print(len(allp))
