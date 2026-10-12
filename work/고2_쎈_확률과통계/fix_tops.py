# -*- coding: utf-8 -*-
"""번호 위 빨간 '사고의 기술' 도장(번호 위 ~20pt)이 top_pad 16 으로는 윗부분이 잘려서,
번호 바로 위 띠(현재 top 에서 8pt 위)에 빨간 잉크가 많으면 top 을 8pt 올린다.
    python fix_tops.py <pdf> <in problems.json> <out problems.json> [--dry]
같은 단 앞 문제의 아래 끝과 body 위끝(52)은 넘지 않는다."""
import json
import sys

import fitz

EXTRA, BODY_TOP, DPI = 8, 52, 100
# 쪽 맨 위(top=52)에 있어 자동으로 못 올리는 도장 문제: 직접 지정 (0494 는 오른쪽 단이라 머리말 '정답 및 풀이' 직전까지만)
OVERRIDE = {(77, "0406"): 40, (93, "0494"): 45}


def red_count(page, x0, x1, y0, y1):
    """→ (빨강 계열 픽셀 수, 주황(B≈0) 픽셀 수). 도장은 빨강(B 40~), 소단원 제목 띠는 주황(B 0)."""
    pix = page.get_pixmap(dpi=DPI, clip=fitz.Rect(x0, y0, x1, y1), colorspace=fitz.csRGB)
    s, red, orange = pix.samples, 0, 0
    for i in range(0, len(s), 3):
        r, g, b = s[i], s[i + 1], s[i + 2]
        if r > 170 and g < 140 and b < 140:
            if b >= 40:
                red += 1
            elif b < 30:
                orange += 1
    return red, orange


def main():
    pdf, src, dst = sys.argv[1:4]
    dry = "--dry" in sys.argv
    doc = fitz.open(pdf)
    data = json.load(open(src, encoding="utf-8"))
    probs = data["problems"]
    prev_bottom = {}
    changed = []
    for p in probs:
        key = (p["page"], p["column"])
        x0, y0, x1, y1 = p["bbox"]
        page = doc[p["pdf_page"]]
        n, o = red_count(page, x0, min(x1, x0 + 90), y0, y0 + 12)
        if (p["page"], p["label"]) in OVERRIDE:
            new_top = OVERRIDE[(p["page"], p["label"])]
            changed.append((p["page"], p["label"], n, o, y0, new_top))
            if not dry:
                p["bbox"][1] = new_top
        elif n >= 40 and n > 2 * o and y0 > BODY_TOP:
            new_top = max(BODY_TOP, y0 - EXTRA, prev_bottom.get(key, 0) + 1)
            changed.append((p["page"], p["label"], n, o, y0, round(new_top, 1)))
            if not dry:
                p["bbox"][1] = round(new_top, 1)
        prev_bottom[key] = y1
    for c in changed:
        print(c)
    print(len(changed), "changed")
    if not dry:
        json.dump(data, open(dst, "w", encoding="utf-8"), ensure_ascii=False, indent=None)


if __name__ == "__main__":
    main()
