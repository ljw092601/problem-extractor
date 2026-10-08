import json, sys
S = r"C:\Users\ljw09\AppData\Local\Temp\claude\C--Users-ljw09-Desktop-promblem-area\c26382be-0e2b-44d9-be28-6fa123aea8e4\scratchpad\rpm"
v = json.load(open(S + r"\vl.json"))
def col(x): return 0 if x < 200 else 1
v.sort(key=lambda d: (d["page"], col(d["x"]), d["y"], d["x"]))
ml = []
for i, d in enumerate(v, 1):
    ml.append({"page": d["page"], "col": col(d["x"]), "y": d["y"], "num": i})
base = json.load(open(S + r"\base.json", encoding="utf-8-sig"))
mode = sys.argv[1]
mg = []
for line in open(S + r"\groups.txt"):
    p, c, y, a, b = line.split()
    mg.append({"page": int(p), "col": int(c), "y": float(y), "range": [int(a), int(b)]})
    mem = [m for m in ml if m["page"] == int(p) and m["col"] == int(c) and int(a) <= m["num"] <= int(b)]
    if len({m["num"] for m in mem}) != int(b) - int(a) + 1 or any(m["y"] < float(y) for m in mem):
        print("check group", line.strip(), [m["num"] for m in mem])
if mode == "vec":
    base["source"] = "text"
    base.pop("text_size", None)
    base["manual_labels"] = ml
    base["manual_groups"] = mg
    base["label_regex"] = "^(ZZZZ)$"
    base["group_regex"] = "^ZZZ(\\d)(\\d)"
    base["rescue"] = False
json.dump(base, open(S + rf"\layout_{mode}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump(ml, open(S + r"\ml.json", "w"), ensure_ascii=False)
print(len(ml))

