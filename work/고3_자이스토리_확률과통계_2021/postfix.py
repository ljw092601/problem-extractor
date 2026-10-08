# -*- coding: utf-8 -*-
"""extract 결과 후처리: 연한 회색 그림 때문에 gap_stop 에서 일찍 끊긴 문제 3개의 아랫끝을 늘린다.
사용: python postfix.py <extract 출력 problems.json> <최종 problems.json>"""
import json
import sys

# (쪽, 단, 번호) → 새 아랫끝 y(pt). 값은 그 문제의 마지막 잉크(보기 줄) + 8
FIX_BOTTOM = {
    (81, "R", 27): 669,    # 가운데 회전판 그림이 연해서 그림·보기가 잘렸음
    (116, "L", 39): 498,   # 주머니 A, B 그림이 연해서 그림·보기가 잘렸음
    (142, "R", 45): 662,   # 카드 칸 그림이 연해서 그 아래 본문·상자·보기가 잘렸음
}

src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8") as f:
    data = json.load(f)
done = set()
for p in data["problems"]:
    key = (p["page"], p["column"], p["num"])
    if key in FIX_BOTTOM:
        p["bbox"][3] = FIX_BOTTOM[key]
        done.add(key)
missing = set(FIX_BOTTOM) - done
if missing:
    sys.exit(f"못 찾음: {missing}")
with open(dst, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)
print(f"{len(done)}개 고침 → {dst}")
