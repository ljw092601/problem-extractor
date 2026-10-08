"""묶음이 다음 단으로 넘어간 경우: 넘어간 소문제 번호 항목들을 하나의 continued 조각으로 바꿈.
spec: [(page, column, group_first_num, [member nums in next column])]"""
import json, sys
S = sys.argv[1]
spec = json.load(open(S + "/postspec.json", encoding="utf-8"))
path = S + "/x/problems.json"
data = json.load(open(path, encoding="utf-8"))
P = data["problems"]
for pg, col, gnum, members in spec:
    items = [p for p in P if p["page"] == pg and p["column"] == col and p["num"] in members and "num_end" not in p]
    assert len(items) == len(members), (pg, members, items)
    g = next(p for p in P if p["num"] == gnum and "num_end" in p)
    x0, x1 = items[0]["bbox"][0], items[0]["bbox"][2]
    top = min(p["bbox"][1] for p in items)
    bot = max(p["bbox"][3] for p in items)
    idx = P.index(items[0])
    for it in items:
        P.remove(it)
    P.insert(idx, {"num": gnum, "label": g["label"], "page": pg, "pdf_page": pg - 1, "column": col,
                   "bbox": [x0, top, x1, bot], "num_end": g["num_end"], "continued": True})
json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(P))
import os
if os.path.exists(S + "/bboxfix.json"):
    for pg, label, idx, val in json.load(open(S + "/bboxfix.json", encoding="utf-8")):
        its = [p for p in P if p["page"] == pg and p["label"] == label]
        assert len(its) == 1, (pg, label)
        its[0]["bbox"][idx] = val
        print("fix", pg, label, its[0]["bbox"])
    json.dump(data, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
