import json, sys
S = sys.argv[1]
v = json.load(open(S + "/vl.json"))
base = {
    "source": "text",
    "pages": [[7, 173]],
    "label_regex": "^(ZZZZ)$",
    "body": [70, 778],
    "columns": [{"x": [43, 297], "label_x": [46, 51]}, {"x": [302, 560], "label_x": [311, 316]}],
    "columns_even": [{"x": [39, 294.5], "label_x": [43, 48]}, {"x": [299, 556], "label_x": [308, 313]}],
    "top_pad": 6,
    "bot_pad": 8,
    "gap_stop": 40,
    "group_gap_stop": 40,
    "drop_outliers": False,
}
import os
extra = json.load(open(S + "/extra.json", encoding="utf-8")) if os.path.exists(S + "/extra.json") else {}
base.update(extra)
ml = []
for o in v:
    ml.append({"page": o["page"], "col": 0 if o["x"] < 250 else 1, "y": o["y"], "num": o["num"]})
base["manual_labels"] = ml
json.dump(base, open(S + "/layout.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(ml))
