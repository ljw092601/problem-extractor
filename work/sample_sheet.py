# -*- coding: utf-8 -*-
"""오케스트레이터 검수용: work/<slug>/problems.json(최종본)에서 무작위 표본을 잘라 모아보기 PNG 로.
    python work/sample_sheet.py <slug> <출력폴더> [표본 수=24]
원본은 SOURCE.txt → work/_src/sources.json 으로 찾는다. 수작업으로 고친 bbox 도 그대로 반영된다."""
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from core import extract  # noqa: E402


def main():
    slug, out = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else 24
    wd = os.path.join(HERE, slug)
    rel = open(os.path.join(wd, "SOURCE.txt"), encoding="utf-8").read().strip().replace("\\", "/")
    local = json.load(open(os.path.join(HERE, "_src", "sources.json"), encoding="utf-8"))[rel]
    probs = json.load(open(os.path.join(wd, "problems.json"), encoding="utf-8"))["problems"]
    lp = os.path.join(wd, "layout.json")
    if os.path.exists(lp) and json.load(open(lp, encoding="utf-8")).get("render_clean"):   # 앱과 똑같이
        for p in probs:
            p["clean"] = True
    rnd = random.Random(slug)
    pick = sorted(rnd.sample(range(len(probs)), min(n, len(probs))))
    paths = extract.contact_sheets(local, [probs[i] for i in pick], out, per_sheet=12, prefix=slug)
    print(f"{slug}: {len(probs)}문제 중 {len(pick)}개 → {len(paths)}장")
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()
