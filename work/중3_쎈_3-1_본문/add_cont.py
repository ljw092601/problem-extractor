# -*- coding: utf-8 -*-
"""problems.json 에 이어진 조각(continued) 넣기.
python add_cont.py <in problems.json> <out problems.json> <spec.json>
spec: [{"after": 740, "page": 103, "col": "R", "bbox": [x0,y0,x1,y1], "num": 742, "num_end": 743}]
after = 이어지는 앞 문제(묶음이면 시작 번호). 그 항목 바로 뒤에 넣는다."""
import json, sys
src, dst, spec = sys.argv[1:4]
d = json.load(open(src, encoding="utf-8"))
sp = json.load(open(spec, encoding="utf-8"))
P = d["problems"]
for s in sp:
    i = next(k for k, p in enumerate(P) if p["num"] == s["after"] and not p.get("continued"))
    prev = P[i]
    a, b = s["num"], s.get("num_end")
    lab = f"{a:04d}" + (f"~{b:04d}" if b else "") + "(이어짐)"
    item = {"num": a, "label": lab, "page": s["page"], "pdf_page": s["page"] - 1, "column": s["col"],
            "bbox": s["bbox"], "continued": True}
    P.insert(i + 1, item)
    print("added after", prev["label"], "->", lab)
json.dump(d, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(P))
