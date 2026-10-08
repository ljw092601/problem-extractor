# -*- coding: utf-8 -*-
"""고3_미래엔_미적분: 두 구역(A 본문 '문제 N', B 중단원 마무리·대단원 평가)의 extract 결과를 합치고,
문제 바로 아래 붙은 풀이를 잘라낸다 (이 PDF 는 자습서라 모든 문제 밑에 풀이가 인쇄되어 있음).

  아래끝 = min(extract 아래끝, 첫 '풀이' 뱃지(연한 주황 테두리) 윗끝 - 3,
               서술형 '문제 이해' 머리글 윗끝 - 3)
  뱃지는 번호 윗끝 + 16pt 아래, 단 왼쪽 띠(A: x 150~232, B: 단 왼쪽 +2 ~ +62)에서 찾는다.

사용: python work\\고3_미래엔_미적분\\merge.py <A extract 폴더> <B extract 폴더> <출력 problems.json>
"""
import json
import os
import re
import sys

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from core import winocr  # noqa: E402

PDF = os.path.join(ROOT, "work", "_src", "고3", "미래엔 미적분.pdf")
DPI = 100
SC = DPI / 72

# 수동 아래끝 (쪽, 번호) → y   (자동으로 못 자른 것)
MANUAL_BOTTOM = {(61, 6): 601, (141, 8): 302, (71, 13): 194}


def salmon(p):
    r, g, b = p[:3]
    return r > 200 and g < 228 and r - b >= 35 and r - g >= 22


def find_badge(pix, x0, x1, y0, y1):
    """[x0,x1]x[y0,y1] 안에서 풀이 뱃지 윗끝(pt). 없으면 None"""
    s, st, n = pix.samples, pix.stride, pix.n
    for ry in range(int(y0 * SC), min(pix.height, int(y1 * SC))):
        cnt = 0
        for rx in range(int(x0 * SC), min(pix.width, int(x1 * SC))):
            o = ry * st + rx * n
            if salmon(s[o:o + 3]):
                cnt += 1
        if cnt >= 6:
            return ry / SC
    return None


def dark_row(pix, ry, x0, x1):
    s, st, n = pix.samples, pix.stride, pix.n
    for rx in range(max(0, int(x0 * SC)), min(pix.width, int(x1 * SC))):
        o = ry * st + rx * n
        if s[o] + s[o + 1] + s[o + 2] < 3 * 150:
            return True
    return False


def footer_top(pix):
    """쪽 맨 아래 꼬리말(쪽 번호·단원명) 윗끝(pt). 없으면 None"""
    ry = min(pix.height, int(785 * SC)) - 1
    while ry > 650 * SC and not dark_row(pix, ry, 30, 580):
        ry -= 1
    bottom = ry
    blank = 0
    top = ry
    while ry > 650 * SC:
        if dark_row(pix, ry, 30, 580):
            top, blank = ry, 0
        else:
            blank += 1
            if blank >= 6 * SC:
                break
        ry -= 1
    if top / SC > 690 and (bottom - top) / SC < 22:
        return top / SC
    return None


def trim_bottom(pix, x0, x1, top, limit):
    """limit 위로 올라가며 마지막 내용 줄 + 4"""
    ry = int(limit * SC)
    while ry > top * SC and not dark_row(pix, ry, x0 + 2, x1 - 2):
        ry -= 1
    return ry / SC + 4


def above_gap(pix, x0, x1, cut):
    """풀이 첫 줄의 키 큰 수식(분수 등)이 뱃지 위로 솟은 부분까지 빼고, 그 위 빈 줄에서 자른다"""
    ry = int(cut * SC) - 1
    start = ry
    while ry > start - 14 * SC and dark_row(pix, ry, x0 + 2, x1 - 2):
        ry -= 1
    if ry <= start - 14 * SC:
        return cut - 3
    blank = 0
    while blank < 3 * SC and ry > start - 30 * SC:
        if dark_row(pix, ry, x0 + 2, x1 - 2):
            return cut - 3                      # 빈 줄이 충분치 않음 → 원래대로
        blank += 1
        ry -= 1
    return min(cut - 3, (ry + blank) / SC + 1)


def find_essay_head(page, x0, x1, y0, y1):
    """서술형 풀이 머리글 '문제 이해' 윗끝(pt)"""
    if y1 - y0 < 30:
        return None
    clip = fitz.Rect(x0, y0, x1, y1)
    pix = page.get_pixmap(dpi=200, clip=clip, colorspace=fitz.csGRAY)
    sc = 72 / 200
    best = None
    for text, a, b, c, d, _ in winocr.ocr_lines(pix, lang="ko"):
        if re.match(r"^\W*(\S[제저체처]\S{0,2}\s*\S?\S?해|\S[제저체처]\s*\S?\s*이|해결|\S?과정(?!과)|답\s*구)", text) and a * sc < 70:
            y = b * sc + y0
            best = y if best is None else min(best, y)
    return best


def main(a_dir, b_dir, out):
    doc = fitz.open(PDF)
    probs = []
    for zone, d in (("A", a_dir), ("B", b_dir)):
        for p in json.load(open(os.path.join(d, "problems.json"), encoding="utf-8"))["problems"]:
            p["_zone"] = zone
            probs.append(p)
    cache = {}
    ncut = nessay = 0
    for p in probs:
        pno = p["pdf_page"]
        if pno not in cache:
            cache = {pno: doc[pno].get_pixmap(dpi=DPI)}
        pix = cache[pno]
        x0, top, x1, bot = p["bbox"]
        ylab = top + 6
        if p["_zone"] == "A":
            bx0, bx1 = 150, 232
        else:
            bx0, bx1 = x0 + 2, x0 + 62
        cut = find_badge(pix, bx0, bx1, ylab + 16, bot)
        e = find_essay_head(doc[pno], x0, x1, ylab + 16, bot if cut is None else cut)
        if e is not None:
            cut = e
            nessay += 1
            print(f"  서술형 머리글: {p['page']}:{p['num']}")
        elif cut is not None:
            ncut += 1
        if cut is not None:
            bot = min(bot, above_gap(pix, x0, x1, cut))
        else:
            print(f"  풀이 표시 못 찾음: {p['page']}쪽 {p['num']}번")
        ft = footer_top(pix)
        if ft is not None and bot > ft - 3:
            bot = trim_bottom(pix, x0, x1, top, ft - 3)
        mb = MANUAL_BOTTOM.get((p["page"], p["num"]))
        if mb:
            bot = mb
        p["bbox"] = [x0, top, x1, round(bot, 1)]
    # 읽는 순서: 쪽 → 단 → y
    probs.sort(key=lambda p: (p["page"], p["column"], p["bbox"][1]))
    for p in probs:
        p.pop("_zone", None)
    json.dump({"pdf": os.path.basename(PDF), "problems": probs}, open(out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"{len(probs)}문제, 풀이 뱃지로 자름 {ncut}, 서술형 머리글로 자름 {nessay}, 못 찾음 {len(probs) - ncut - nessay}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
