import fitz, re, json, sys
from collections import Counter
d = fitz.open(sys.argv[1])
out = []
xs = Counter()
GRAY = 10987948
for pno in range(len(d)):
    pg = d[pno]
    sp = []
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                t = s["text"].strip()
                if abs(s["size"] - 11.1) < 0.3 and re.fullmatch(r"\d{1,4}", t):
                    sp.append((t, s["bbox"], s["color"]))
    for t, bb, c in sp:
        if c != GRAY:
            continue
        nxt = [u for u in sp if u[2] != GRAY and abs(u[1][1] - bb[1]) < 1 and -2 < u[1][0] - bb[2] < 3]
        if len(nxt) != 1:
            print("??", pno + 1, t, bb, nxt)
            continue
        s4 = t + nxt[0][0]
        if len(s4) != 4:
            print("len", pno + 1, s4)
        out.append({"page": pno + 1, "x": round(bb[0], 1), "y": round(bb[1], 1), "num": int(s4)})
        xs[(pno % 2, round(bb[0]))] += 1
    # colored-only spans with no gray prefix
    for t, bb, c in sp:
        if c == GRAY:
            continue
        prv = [u for u in sp if u[2] == GRAY and abs(u[1][1] - bb[1]) < 1 and -2 < bb[0] - u[1][2] < 3]
        if not prv:
            if len(t) == 4:
                out.append({"page": pno + 1, "x": round(bb[0], 1), "y": round(bb[1], 1), "num": int(t)})
                xs[(pno % 2, round(bb[0]))] += 1
            else:
                print("orphan", pno + 1, t, [round(v, 1) for v in bb])
json.dump(out, open(sys.argv[2], "w"), ensure_ascii=False)
print(len(out))
print(sorted(xs.items()))
nums = sorted(o["num"] for o in out)
print("min", nums[0], "max", nums[-1], "dups", [n for n in set(nums) if nums.count(n) > 1][:30])
print("missing", [n for n in range(nums[0], nums[-1] + 1) if n not in set(nums)][:200])
