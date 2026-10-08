# -*- coding: utf-8 -*-
"""layout_main(객관식·단답 01~20) + layout_seosul(서술형 1~4, 수동 위치) 결과를 합쳐 problems.json 으로.
서술형은 label 을 '서술형N' 으로, column 을 'R' 로 (오른쪽 단에만 있음). (저장소 코드는 안 고침)
usage: python merge.py"""
import json, os
H = os.path.dirname(os.path.abspath(__file__))
m = json.load(open(os.path.join(H, "run_main", "problems.json"), encoding="utf-8"))["problems"]
s = json.load(open(os.path.join(H, "run_seosul", "problems.json"), encoding="utf-8"))["problems"]
for p in s:
    p["label"] = f"서술형{p['num']}"
    p["column"] = "R"
allp = sorted(m + s, key=lambda p: (p["page"], 0 if p["column"] == "L" else 1, p["bbox"][1]))
json.dump({"pdf": "94 실전모의고사 중간고사대비 중3.PDF", "problems": allp},
          open(os.path.join(H, "problems.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
rep = "== main\n" + open(os.path.join(H, "run_main", "report.txt"), encoding="utf-8").read() + \
      "== seosul (서술형, 수동 위치)\n" + open(os.path.join(H, "run_seosul", "report.txt"), encoding="utf-8").read()
open(os.path.join(H, "report.txt"), "w", encoding="utf-8").write(f"합계 {len(allp)}개\n\n" + rep)
print(len(allp))
