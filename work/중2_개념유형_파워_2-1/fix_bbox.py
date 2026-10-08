# -*- coding: utf-8 -*-
# python fix_bbox.py <extract 결과 problems.json> <slug 폴더>
#   추출 결과를 복사하면서 gap_stop 때문에 아래가 잘린 문제의 아랫변을 직접 내린다 (코드 수정 아님).
#   65쪽 38번: 소문항 (1) 과 (2) 사이 여백이 커서 (2) 가 빠짐 → 아랫변 683.2 (gap_stop 80 으로 뽑았을 때 값)
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
FIX = {(65, 38): 683.2}
src, root = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as f:
    d = json.load(f)
n = 0
for p in d["problems"]:
    k = (p["page"], p["num"])
    if k in FIX:
        print("fix", k, p["bbox"][3], "->", FIX[k])
        p["bbox"][3] = FIX[k]
        n += 1
assert n == len(FIX), n
with open(os.path.join(root, "problems.json"), "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
print("problems", len(d["problems"]))
