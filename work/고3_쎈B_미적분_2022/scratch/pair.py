# -*- coding: utf-8 -*-
"""refs.json → 단원별 기준값(쎈 번호 − 문제 번호) 추정, 문제 번호·위치(manual_labels) 만들기.
    python pair.py <refs.json> <out manual.json> [extra.json]
후보 = 쎈 번호(기준값 빼서) + 2자리 번호 OCR. 쪽·단·y 순서로 번호가 늘어나는 가장 긴(쎈 번호 가중) 부분열만 채택.
extra.json: {"단원번호": [{"page","col","y","num"}, ...]} 사람이 직접 확인해 넣은 번호 (우선)."""
import json, sys
from collections import Counter
R = {int(k): v for k, v in json.load(open(sys.argv[1])).items()}
UNITS = [(7, 19), (21, 34), (37, 46), (49, 61), (65, 75), (77, 88), (91, 102), (105, 115), (119, 129), (131, 142)]
MID = 297
EXTRA = json.load(open(sys.argv[3], encoding="utf-8")) if len(sys.argv) > 3 else {}
manual = []
for ui, (a, b) in enumerate(UNITS):
    votes = Counter()
    for p in range(a, b + 1):
        for n, lx, ly, _ in R[p]["labs"]:
            for r, rx, ry in R[p]["refs"]:
                if (lx < MID) == (rx < MID) and abs(ry - ly - 4) < 8:
                    votes[r - n] += 1
    base = votes.most_common(1)[0][0]
    cand = []
    for p in range(a, b + 1):
        for r, rx, ry in R[p]["refs"]:
            n = r - base
            if 1 <= n <= 140 and 40 < ry < 780:
                cand.append((p, 0 if rx < MID else 1, ry - 4, n, 3))
        for n, lx, ly, _ in R[p]["labs"]:
            if 1 <= n and 40 < ly < 775:
                cand.append((p, 0 if lx < MID else 1, ly, n, 1))
    for e in EXTRA.get(str(ui + 1), []):
        cand.append((e["page"], e["col"], e["y"], e["num"], 100))
    cand.sort()
    # 같은 자리(쪽·단·y±12)·같은 번호 합치기
    merged = []
    for c in cand:
        m = next((i for i, d in enumerate(merged) if d[0] == c[0] and d[1] == c[1] and d[3] == c[3] and abs(d[2] - c[2]) < 12), None)
        if m is None:
            merged.append(list(c))
        else:
            d = merged[m]
            if c[4] > d[4] or (c[4] == d[4] and c[4] == 1):
                d[2] = c[2] if c[4] >= d[4] else d[2]
            d[4] += c[4]
    # 가중 LIS (번호 엄격 증가)
    n = len(merged)
    best = [0] * n
    prev = [-1] * n
    for i in range(n):
        best[i] = merged[i][4]
        for j in range(i):
            if merged[j][3] < merged[i][3] and best[j] + merged[i][4] > best[i]:
                best[i] = best[j] + merged[i][4]
                prev[i] = j
    i = max(range(n), key=lambda k: best[k])
    chosen = []
    while i >= 0:
        chosen.append(merged[i])
        i = prev[i]
    chosen.reverse()
    nums = [c[3] for c in chosen]
    top = max(nums)
    miss = [k for k in range(1, top + 1) if k not in nums]
    weak = [(c[0], c[3]) for c in chosen if c[4] < 3]
    rej = [(c[0], c[3], c[4]) for c in merged if c not in chosen and c[4] >= 3]
    print(f"단원 {ui+1} 쪽 {a}-{b} 기준 {base} 문제 {len(chosen)} 끝 {top}")
    print("   빠짐", miss, "| 2자리만", weak, "| 버린 쎈번호", rej)
    for c in chosen:
        manual.append({"page": c[0], "col": c[1], "y": round(c[2]), "num": c[3]})
json.dump(manual, open(sys.argv[2], "w", encoding="utf-8"))
print("합계", len(manual))
