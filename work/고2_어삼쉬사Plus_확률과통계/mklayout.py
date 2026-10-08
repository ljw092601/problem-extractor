import json, sys
labels = json.load(open(sys.argv[1], encoding="utf-8"))
base = json.load(open(sys.argv[2], encoding="utf-8"))
base["manual_labels"] = labels
with open(sys.argv[3], "w", encoding="utf-8") as f:
    json.dump(base, f, ensure_ascii=False, indent=1)
