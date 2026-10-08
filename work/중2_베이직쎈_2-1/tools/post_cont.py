import sys, json
# post_cont.py in_problems.json conts.json out_problems.json
# 단을 넘어간 묶음 조각(conts: {page, col, num, root:[page,col,[a,b]]}) 을 "continued": true 로 표시하고 번호를 앞 묶음과 같게.
src = json.load(open(sys.argv[1], encoding="utf-8"))
conts = json.load(open(sys.argv[2], encoding="utf-8"))
ps = src["problems"]
byk = {}
for p in ps:
    byk.setdefault((p["page"], p["column"], p["num"]), []).append(p)
n = 0
for c in conts:
    col = "LR"[c["col"]]
    piece = byk.get((c["page"], col, c["num"]))
    rp, rc, rng = c["root"]
    root = byk.get((rp, "LR"[rc], rng[0]))
    if not piece or not root:
        print("NOT FOUND", c); continue
    piece, root = piece[0], root[0]
    assert root.get("num_end") == rng[1], (root, rng)
    i, j = ps.index(root), ps.index(piece)
    assert j > i
    # 이어진 조각은 바로 앞 항목이 같은 묶음(루트 또는 앞 조각)이어야 함
    prev = ps[j - 1]
    assert prev is root or (prev.get("continued") and prev["num"] == root["num"]), (prev, piece)
    piece["continued"] = True
    piece["num"] = root["num"]
    piece["num_end"] = root["num_end"]
    piece["label"] = root["label"]
    n += 1
json.dump(src, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("continued", n, "of", len(conts), "problems", len(ps), "-> 실제 문제 수", len(ps) - n)
