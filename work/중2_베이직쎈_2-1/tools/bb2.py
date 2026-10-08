import sys, json
# bb2.py blobs.json out_prefix [extra.json]
# 중2 베이직쎈: classify colored blobs -> labels O(orange drill)/G(green 유형)/B(blue 기출) + I (olive ▶ icon).
# number (OCR + sequence), fill gaps from OCR tokens, groups = icon + following O labels in same column.
raw = json.load(open(sys.argv[1], encoding="utf-8"))
prefix = sys.argv[2]
extra = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else {}
TOP_PAD = 12
blobs = [b for b in raw if not b.get("tok")]
toks = [t for t in raw if t.get("tok")]
K = lambda b: (b["page"], b["col"], b["y"])


def cls(b):
    r, g, bl = b["rgb"]
    w, h = b["w"], b["h"]
    if 9.5 <= h <= 12.5 and 7 <= w <= 19 and b["x"] < [[60, 332], [52, 324]][b["page"] % 2 == 0][b["col"]] + 6 and 145 <= r <= 190 and 120 <= g <= 160 and 45 <= bl <= 95 and r > g > bl:
        return "I"
    lx0 = [[60, 332], [52, 324]][b["page"] % 2 == 0][b["col"]]
    if b["x"] >= lx0 + 9:
        return None
    wmax = 28 if b.get("ocr") else 19.5
    if not (9.5 <= h <= 13 and 11.5 <= w <= wmax) or b["fill"] > 0.8 or b["fill"] < 0.25:
        return None
    if r > 185 and r - bl > 80 and g < 150:
        return "O"
    if g > r + 15 and g > bl + 25 and r < 150:
        return "G"
    if bl > r + 30 and bl > g + 5 and r < 170:
        return "B"
    return None


items = []
for b in blobs:
    c = cls(b)
    if c:
        b["cls"] = c
        items.append(b)
items.sort(key=K)
# badge (빈출 etc.) right above a label -> drop the upper one
items = [b for b in items if not (b["cls"] != "I" and any(x is not b and x["cls"] != "I" and x["page"] == b["page"] and x["col"] == b["col"]
                                                         and 6 <= x["y"] - b["y"] <= 18 for x in items))]
for d in extra.get("drop", []):
    items = [b for b in items if not (b["page"] == d[0] and b["col"] == d[1] and abs(b["y"] - d[2]) < 3)]
for a in extra.get("add", []):
    items.append({"page": a["page"], "col": a["col"], "y": a["y"], "cls": a.get("cls", "O"), "ocr": [a["num"]], "manual": True})
for f in extra.get("fix", []):
    for b in items:
        if b["page"] == f[0] and b["col"] == f[1] and abs(b["y"] - f[2]) < 3:
            b["ocr"] = [f[3]]
for ic in extra.get("icons", []):
    items.append({"page": ic[0], "col": ic[1], "y": ic[2], "cls": "I", "ocr": []})
items.sort(key=K)


def number(labels):
    known = []
    for b in labels:
        o = sorted(set(b["ocr"]))
        known.append(o[0] if len(o) == 1 else (o if o else None))
    prev = 0
    for i, b in enumerate(labels):
        k = known[i]
        b.pop("guess", None)
        if isinstance(k, list):
            k = prev + 1 if prev + 1 in k else (1 if 1 in k else k[0])
        if k is None:
            j = i + 1
            while j < len(labels) and not isinstance(known[j], int):
                j += 1
            if j < len(labels) and isinstance(known[j], int) and known[j] - (j - i) >= 1 and known[j] <= prev:
                k = known[j] - (j - i)
            else:
                k = prev + 1
            b["guess"] = True
        b["num"] = k
        prev = k


labels = [b for b in items if b["cls"] in ("O", "G", "B")]
number(labels)
added = []
for a, b in zip(labels, labels[1:]):
    if a.get("guess") or b.get("guess"):
        continue
    if 2 <= b["num"] - a["num"] <= 8:
        for t in toks:
            if a["num"] < t["num"] < b["num"] and K(a) < K(t) < K(b) and all(abs(t["y"] - x["y"]) > 8 or t["col"] != x["col"] or t["page"] != x["page"] for x in labels):
                if not any(x["page"] == t["page"] and x["col"] == t["col"] and abs(x["y"] - t["y"]) < 8 for x in added):
                    added.append({"page": t["page"], "col": t["col"], "y": t["y"], "cls": a["cls"], "ocr": [t["num"]], "fromtok": True})
items = sorted(items + added, key=K)
labels = [b for b in items if b["cls"] in ("O", "G", "B")]
number(labels)

anom = []
for a, b in zip(labels, labels[1:]):
    if b["num"] != a["num"] + 1 and b["num"] != 1:
        anom.append((a["page"], a["col"], a["y"], a["num"], "->", b["page"], b["col"], b["y"], b["num"], b["cls"], "g" if b.get("guess") else ""))

# groups: icon + following O labels in the same column (stop at G/B label or next icon)
groups = []
cur = None
last_key = None
def flush():
    global cur
    if cur and cur["nums"]:
        groups.append(cur)
    cur = None
colstart = []   # O labels at top of a column right after a column that ended inside a group (possible continuation)
for e in items:
    key = (e["page"], e["col"])
    if key != last_key:
        if cur is not None and cur["nums"]:
            cur["open_end"] = True
        prev_open = cur
        flush()
        last_key = key
    else:
        prev_open = None
    if e["cls"] == "I":
        flush()
        cur = {"page": e["page"], "col": e["col"], "y": round(e["y"] + TOP_PAD - 3, 1), "nums": []}
        continue
    if e["cls"] == "O":
        if cur is not None:
            cur["nums"].append(e["num"])
        elif prev_open is not None:
            colstart.append({"page": e["page"], "col": e["col"], "y": e["y"], "num": e["num"], "after": [prev_open["page"], prev_open["col"], prev_open["nums"]]})
            if [e["page"], e["col"]] not in extra.get("indep", []):
                cur = {"page": e["page"], "col": e["col"], "y": round(e["y"] - 1, 1), "nums": [e["num"]],
                       "root": prev_open.get("root", prev_open)}
        continue
    flush()
flush()

pos = {id(b): i for i, b in enumerate(labels)}
for g in groups:
    mx = max(g["nums"])
    lastlab = [b for b in labels if b["page"] == g["page"] and b["col"] == g["col"] and b["cls"] == "O" and b["num"] == mx]
    if not lastlab:
        continue
    i = pos[id(lastlab[-1])]
    if i + 1 < len(labels):
        nx = labels[i + 1]
        if nx["cls"] == "O" and 2 <= nx["num"] - mx <= 4:
            g["ext"] = nx["num"] - 1
for g in groups:
    g["rng"] = [min(g["nums"]), g.get("ext", max(g["nums"]))]
for g in groups:
    if "root" in g:
        r = g["root"]
        r["rng"][1] = max(r["rng"][1], g["rng"][1])
man_labels = [{"page": b["page"], "col": b["col"], "y": b["y"], "num": b["num"]} for b in labels]
man_groups = [{"page": g["page"], "col": g["col"], "y": g["y"], "range": g["rng"]} for g in groups]
conts = [{"page": g["page"], "col": g["col"], "num": g["rng"][0], "root": [g["root"]["page"], g["root"]["col"], g["root"]["rng"]]} for g in groups if "root" in g]
json.dump(conts, open(prefix + "_conts.json", "w", encoding="utf-8"), ensure_ascii=False)
print("continuations", len(conts), conts)
print("extended groups", [(g["page"], g["col"], g["nums"], g["ext"]) for g in groups if "ext" in g])
bad = [(g["page"], g["col"], g["nums"]) for g in groups if max(g["nums"]) - min(g["nums"]) + 1 != len(g["nums"]) or len(set(g["nums"])) != len(g["nums"])]
json.dump({"manual_labels": man_labels, "manual_groups": man_groups}, open(prefix + "_manual.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump(labels, open(prefix + "_labels_debug.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump(colstart, open(prefix + "_colstart.json", "w", encoding="utf-8"), ensure_ascii=False)
print("labels", len(labels), "icons", sum(1 for b in items if b["cls"] == "I"), "groups", len(groups),
      "guessed", sum(1 for b in labels if b.get("guess")), "from tokens", len(added))
print("classes", {c: sum(1 for b in labels if b["cls"] == c) for c in "OGB"})
print("anomalies", len(anom))
for a in anom:
    print("  ", a)
print("bad groups", bad)
print("column-start O after open group:", len(colstart))
for c in colstart:
    print("  ", c)



