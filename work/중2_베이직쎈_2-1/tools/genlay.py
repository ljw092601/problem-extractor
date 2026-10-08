import sys, json
# genlay.py base_layout.json manual.json pages_a-b out.json  -> scratch layout with manual labels/groups for page range
base = json.load(open(sys.argv[1], encoding="utf-8"))
man = json.load(open(sys.argv[2], encoding="utf-8"))
a, b = map(int, sys.argv[3].split("-"))
out = sys.argv[4]
lay = {k: v for k, v in base.items() if k not in ("manual_labels", "manual_groups")}
lay["pages"] = [[a, b]]
lay["label_regex"] = "^Z(\\d)$"
lay["group_regex"] = "^Z(\\d)Z(\\d)$"
lay["drop_outliers"] = False
lay["manual_labels"] = [{"page": m["page"], "col": m["col"], "y": m["y"], "num": m["num"]} for m in man["manual_labels"] if a <= m["page"] <= b]
lay["manual_groups"] = [g for g in man["manual_groups"] if a <= g["page"] <= b]
lines = ["{"]
keys = [k for k in lay if k not in ("manual_labels", "manual_groups")]
for k in keys:
    lines.append(f'  {json.dumps(k)}: {json.dumps(lay[k], ensure_ascii=False)},')
lines.append('  "manual_groups": [')
lines.append(",\n".join("    " + json.dumps(g, separators=(",", ":")) for g in lay["manual_groups"]))
lines.append('  ],')
lines.append('  "manual_labels": [')
lines.append(",\n".join("    " + json.dumps(m, separators=(",", ":")) for m in lay["manual_labels"]))
lines.append('  ]')
lines.append("}")
open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
json.load(open(out, encoding="utf-8"))
print(out, len(lay["manual_labels"]), "labels", len(lay["manual_groups"]), "groups")
