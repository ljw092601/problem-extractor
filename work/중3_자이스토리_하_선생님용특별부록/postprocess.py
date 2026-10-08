# 후처리 (layout top_pad=8 가정):
#  1) 짝수 쪽 머리 띠(y<=93) 잘라내기: bbox y0 >= 95
#  2) '서술형'/'창의적 서술형' 탭(외곽선 글자 = 검은 채움 도형)이 번호 위에 있으면 문제 위쪽을 탭까지 늘리고,
#     같은 단 앞 문제의 아래가 탭을 물면 탭 위에서 자른다.
import json, sys
import fitz

TOP_PAD = 8
p, pdf = sys.argv[1], sys.argv[2]
d = json.load(open(p, encoding="utf-8"))
doc = fitz.open(pdf)
cache = {}


def glyphs(pno):
    if pno not in cache:
        out = []
        for dr in doc[pno].get_drawings():
            r = dr["rect"]
            if dr["type"] == "f" and dr.get("fill") == (0.0, 0.0, 0.0) and r.width < 12 and r.height < 12:
                out.append(r)
        cache[pno] = out
    return cache[pno]


probs = d["problems"]
ntab = nclamp = ncut = 0
for i, q in enumerate(probs):
    x0, y0, x1, y1 = q["bbox"]
    label_top = y0 + TOP_PAD
    band = [r for r in glyphs(q["pdf_page"])
            if x0 + 5 < r.x0 < x0 + 110 and label_top - 40 < r.y0 < label_top - 4]
    if len(band) >= 6:
        tab_top = min(r.y0 for r in band) - 7          # 탭 테두리 포함
        q["bbox"][1] = round(tab_top, 1)
        ntab += 1
        for pr in probs[:i][::-1]:
            if pr["page"] == q["page"] and pr["column"] == q["column"]:
                if pr["bbox"][3] > tab_top - 1:
                    pr["bbox"][3] = round(tab_top - 2, 1)
                    ncut += 1
                break
    if q["page"] % 2 == 0 and q["bbox"][1] < 95:
        q["bbox"][1] = 95
        nclamp += 1
json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("tabs", ntab, "prev cut", ncut, "header clamp", nclamp)
