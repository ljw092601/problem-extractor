# -*- coding: utf-8 -*-
# merge_parts.py 뒤에 실행: OCR 이 번호를 잘못 읽은 항목 바로잡기 (영역은 맞음)
#   7쪽 R '66' → 6  (쌍둥이 기출 6번, 옆 글자와 붙어 66 으로 읽힘)
import json, os, sys
root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
fn = os.path.join(root, "problems.json")
with open(fn, encoding="utf-8") as f:
    d = json.load(f)
n = 0
for p in d["problems"]:
    if p["page"] == 7 and p["column"] == "R" and p["num"] == 66:
        p["num"], p["label"] = 6, "6"
        n += 1
with open(fn, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=1)
print("fixed", n)
