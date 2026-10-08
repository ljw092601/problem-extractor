# -*- coding: utf-8 -*-
# 개념유형 개념 2-2 (스캔본 + OCR 글자층): 문제 번호 위치를 그림에서 찾는다.
#   개념 쪽: '필수 문제' 번호 알약(보라색, 폭 15~26pt) / 유제 N-k 앞 보라 막대(폭 < 6pt)
#   step1(쏙쏙 개념 익히기·한번 더 연습): 번호 띠(x 115~160)의 굵은 검은 숫자
#   step2(탄탄 단원 다지기): 두 단의 번호 띠의 굵은 숫자
# 번호 값은 Windows OCR(core.winocr, 읽기만)로 읽고, 못 읽으면 순서로 채운다.
# python detect22.py <pdf> <out.json>
import sys, json, re
import fitz, numpy as np, cv2
sys.path.insert(0, r"C:\Users\ljw09\Desktop\promblem_area")
from core import winocr
sys.stdout.reconfigure(encoding="utf-8")

pdf, out = sys.argv[1], sys.argv[2]
d = fitz.open(pdf)
Z = 3.0

def R(a, b):
    return list(range(a, b + 1))

CONCEPT = [9, 10, 11, 14, 15, 16, 19, 20, 21, 23, 24, 25, 37, 38, 40, 41, 42, 44, 45, 46, 47, 50, 51, 52, 54, 55,
           67, 68, 69, 71, 72, 74, 75, 76, 78, 79, 91, 92, 93, 94, 97, 98, 99, 101, 102, 103, 105, 106, 107, 108,
           121, 122, 123, 124, 127, 128, 139, 140, 141, 142, 145, 146, 147, 148, 159, 160, 161, 162, 165, 166, 167]
STEP1 = [12, 13, 17, 18, 22, 26, 39, 43, 48, 49, 53, 56, 70, 73, 77, 80, 81, 95, 96, 100, 104, 109, 110,
         125, 126, 129, 143, 144, 149, 163, 164, 168, 169]
STEP2 = R(28, 30) + R(57, 60) + R(82, 84) + R(111, 114) + R(130, 132) + R(150, 152) + R(170, 172)


def render(p):
    pix = d[p - 1].get_pixmap(matrix=fitz.Matrix(Z, Z))
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].astype(int)
    return a, pix


def comps(mask, x0, x1, y0=55, y1=765):
    sub = np.zeros_like(mask, dtype=np.uint8)
    X0, X1, Y0, Y1 = int(x0 * Z), int(x1 * Z), int(y0 * Z), int(y1 * Z)
    sub[Y0:Y1, X0:X1] = mask[Y0:Y1, X0:X1]
    n, lab, st, _ = cv2.connectedComponentsWithStats(sub, 8)
    out = []
    for i in range(1, n):
        x, y, w, h, area = st[i]
        out.append((x / Z, y / Z, w / Z, h / Z, area / Z / Z))
    return out


def ocr_num(pix_page, x0, y0, x1, y1, invert=False):
    clip = fitz.Rect(x0, y0, x1, y1)
    return None


def ocr_clip(p, x0, y0, x1, y1, invert=False, zoom=6):
    pg = d[p - 1]
    pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=fitz.Rect(x0, y0, x1, y1))
    if invert:
        pix.invert_irect(pix.irect)
    # 여백을 붙여 OCR 이 잘 읽게
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    pad = 40
    big = np.full((a.shape[0] + 2 * pad, a.shape[1] + 2 * pad, 3), 255, np.uint8)
    big[pad:pad + a.shape[0], pad:pad + a.shape[1]] = a
    g = cv2.cvtColor(big, cv2.COLOR_RGB2GRAY)
    g = cv2.cvtColor(g, cv2.COLOR_GRAY2RGB)
    p2 = fitz.Pixmap(fitz.csRGB, g.shape[1], g.shape[0], g.tobytes(), False)
    words = winocr.ocr_pixmap(p2)
    return " ".join(w[0] for w in words)


def digits(t):
    t = t.replace("O", "0").replace("o", "0").replace("l", "1").replace("I", "1").replace("|", "1").replace("S", "5")
    m = re.findall(r"\d+", t)
    return m


res = []
for p in CONCEPT:
    a, pix = render(p)
    Rr, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    purple = ((B - Rr > 25) & (B - G > 18) & (B < 225)).astype(np.uint8)
    cs = comps(purple, 105, 172)
    pills = [c for c in cs if 12.5 <= c[3] <= 16.5 and 14 <= c[2] <= 32 and c[4] > 0.6 * c[2] * c[3]]
    bars = [c for c in cs if 7 <= c[3] <= 15.5 and 0.8 <= c[2] <= 3.5 and c[4] > 0.6 * c[2] * c[3]]
    # 같은 줄의 가는 조각 중 가장 왼쪽(= ▌ 표시)만, 알약 옆 조각은 버림
    bars = [b for b in bars if not any(abs(b[1] - q[1]) < 5 and q[0] < b[0] for q in bars)]
    bars = [b for b in bars if not any(abs(b[1] - q[1]) < 8 and q[0] <= b[0] <= q[0] + q[2] + 10 for q in pills)]
    for (x, y, w, h, area) in pills:
        res.append({"page": p, "kind": "필수", "x": round(x, 1), "y": round(y, 1), "h": round(h, 1),
                    "ocr": "", "num": None})
    for (x, y, w, h, area) in bars:
        t = ocr_clip(p, x + w + 1, y - 3, x + w + 34, y + h + 3)
        n = digits(t)
        res.append({"page": p, "kind": "유제", "x": round(x, 1), "y": round(y, 1), "h": round(h, 1),
                    "ocr": t, "num": int(n[0]) if n else None})

def dark_labels(p, a, bands, kind):
    g = a.mean(axis=2)
    dark = (g < 120).astype(np.uint8)
    # 숫자 두 자리(예: 12)가 이어지게 가로로 조금 불린다
    dark = cv2.dilate(dark, np.ones((1, int(2.5 * Z)), np.uint8))
    for ci, (x0, x1) in enumerate(bands):
        cs = sorted([c for c in comps(dark, x0, x1) if 11 <= c[3] <= 24 and 3 <= c[2] <= 30 and c[0] - x0 < 30],
                    key=lambda c: (round(c[1]), c[0]))
        merged = []
        for c in cs:                                     # 두 자리 숫자가 두 조각으로 나뉜 것 합치기
            if merged and abs(merged[-1][1] - c[1]) < 3 and c[0] - (merged[-1][0] + merged[-1][2]) < 6:
                m = merged[-1]
                x_ = min(m[0], c[0]); x2 = max(m[0] + m[2], c[0] + c[2])
                merged[-1] = (x_, min(m[1], c[1]), x2 - x_, max(m[3], c[3]), m[4] + c[4])
            else:
                merged.append(c)
        for (x, y, w, h, area) in merged:
            if True:
                t = ocr_clip(p, x - 2, y - 2, x + w + 2, y + h + 2)
                n = digits(t)
                res.append({"page": p, "kind": kind, "col": ci, "x": round(x, 1), "y": round(y, 1), "h": round(h, 1),
                            "w": round(w, 1), "ocr": t, "num": int(n[0]) if n else None})

for p in STEP1:
    a, pix = render(p)
    dark_labels(p, a, [(115, 162)], "step1")
for p in STEP2:
    a, pix = render(p)
    even = p % 2 == 0
    bands = [(25, 60), (286, 322)] if even else [(38, 72), (300, 334)]
    dark_labels(p, a, bands, "step2")

for r in res:
    print(r["page"], r["kind"], r.get("col", 0), r["x"], r["y"], r["h"], repr(r["ocr"]), r["num"])
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("found", len(res))
