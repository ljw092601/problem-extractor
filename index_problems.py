# -*- coding: utf-8 -*-
"""
문제집 스캔/PDF에서 문제 번호와 위치를 자동 색인한다.
- 문제 번호 라벨(예: 01, 02 ...)을 텍스트 레이어에서 찾아 위치를 잡는다.
- 각 문제 영역 = [단 좌우 경계] x [번호 시작 y ~ 같은 단 다음 문제 시작 y]
- 아래쪽 빈 여백은 실제 내용 끝까지만 남기고 잘라낸다(content trim).
결과: problems_index.json
"""
import fitz, re, json, os, glob

HERE = os.path.dirname(os.path.abspath(__file__))


def find_pdf():
    """스크립트와 같은 폴더에서 원본 문제집 PDF 한 개를 자동으로 찾는다.
    출력 파일(selected_*, _로 시작)은 제외한다."""
    def is_output(name):
        n = os.path.basename(name).lower()
        return n.startswith("selected_") or n.startswith("_")
    pdfs = [p for p in glob.glob(os.path.join(HERE, "*"))
            if p.lower().endswith(".pdf") and not is_output(p)]
    if not pdfs:
        raise SystemExit("이 폴더에 원본 PDF가 없습니다. 문제집 PDF를 넣어 주세요.")
    if len(pdfs) > 1:
        print("원본 PDF가 여러 개입니다. 첫 번째를 사용합니다:", os.path.basename(pdfs[0]))
    return pdfs[0]


# ---- 설정 (이 문제집에 맞춤; 다른 문제집이면 값만 조정) -------------------
PDF = find_pdf()
OUT_JSON = os.path.join(HERE, "problems_index.json")

LABEL_SIZE = 13.0          # 문제 번호 라벨 폰트 크기 (해설/헤더 숫자와 구분)
SIZE_TOL   = 0.8
LABEL_X    = {"L": 54, "R": 312}   # 각 단 번호 라벨의 x0 위치(앵커). 여기서 벗어난 숫자는 라벨 아님
LABEL_X_TOL = 20           # 앵커 허용 오차(pt)
BADGE_TEXT = "서술형"       # 문제 번호 위에 붙는 뱃지 텍스트(없으면 자동으로 무시됨)
COL_DIVIDER = 297.5        # 좌/우 단 경계 x (뱃지 열 판정용)
LEFT_X   = (40, 292)       # 좌단 crop x 범위
RIGHT_X  = (303, 556)      # 우단 crop x 범위
TOP_PAD  = 8               # 번호 위쪽 여백
BOT_PAD  = 10              # 내용 아래 여백
GAP_STOP = 40              # 내용 뒤 이만큼(pt) 이상 비면 문제 끝으로 간주(다음 문제 헤더 침범 방지)
COL_BOTTOM = 805           # 단 맨 아래 한계(푸터 위)
TRIM_DPI = 150             # 여백 트리밍용 렌더 해상도
# ---------------------------------------------------------------------------


def find_badges(page):
    """서술형 뱃지 목록: (column, top_y). 아이콘(이미지)+'서술형' 텍스트를 한 뱃지로 묶는다."""
    dct = page.get_text("dict")
    images = [b["bbox"] for b in dct["blocks"] if b.get("type") == 1]
    badges = []
    if not BADGE_TEXT:
        return badges
    for r in page.search_for(BADGE_TEXT):
        col = "L" if r.x0 < COL_DIVIDER else "R"
        top = r.y0
        # 바로 위(≤25pt)에 같은 단 아이콘 이미지가 있으면 그 위를 뱃지 상단으로
        for ix0, iy0, ix1, iy1 in images:
            icol = "L" if ix0 < COL_DIVIDER else "R"
            if icol == col and 0 <= (r.y0 - iy1) <= 25:
                top = min(top, iy0)
        badges.append((col, top))
    return badges


def find_labels(page, badges):
    """문제 라벨 목록: (num, column, eff_start, label_y0).
    eff_start = 자기 뱃지가 있으면 뱃지 상단, 없으면 라벨 y0."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                txt = span["text"].strip()
                m = re.fullmatch(r"(\d{1,2})\.?", txt)   # '01' 또는 '1.' 모두 허용
                if not m or abs(span["size"] - LABEL_SIZE) > SIZE_TOL:
                    continue
                x0, y0, x1, y1 = span["bbox"]
                # 라벨 x위치가 어느 단 앵커에 가까운지로 열 판정(아니면 라벨 아님 → 제외)
                col = next((c for c, ax in LABEL_X.items()
                            if abs(x0 - ax) <= LABEL_X_TOL), None)
                if col is None:
                    continue
                eff = y0
                # 라벨 바로 위(≤45pt)에 같은 단 뱃지가 있으면 이 문제 소유
                for bcol, btop in badges:
                    if bcol == col and 0 <= (y0 - btop) <= 45 and btop < y0:
                        eff = min(eff, btop)
                out.append((int(m.group(1)), col, eff, y0))
    return out


def content_bottom(pix, x_range, y_top, y_limit, page_h):
    """[x_range] x [y_top..y_limit] 안에서 '위에서부터 이어지는 내용 블록'의 바닥 y(pt).
    큰 세로 여백(GAP_STOP pt 이상)을 만나면 거기서 끊는다 → 다음 문제의 헤더/뱃지 침범 방지."""
    scale = pix.height / page_h
    px0 = max(0, int(x_range[0] * scale))
    px1 = min(pix.width, int(x_range[1] * scale))
    ry0 = max(0, int(y_top * scale))
    ry1 = min(pix.height, int(y_limit * scale))
    n = pix.n                      # 채널 수
    samples = pix.samples
    stride = pix.stride
    gap_stop_px = GAP_STOP * scale
    last_dark = ry0
    blank_run = 0
    started = False
    for ry in range(ry0, ry1):
        row = ry * stride
        dark = False
        # 가로로 몇 픽셀씩 건너뛰며 검사(속도)
        for px in range(px0, px1, 2):
            idx = row + px * n
            # 회색값 대략 계산 (RGB 평균)
            v = samples[idx] if n < 3 else (samples[idx] + samples[idx+1] + samples[idx+2]) // 3
            if v < 160:            # 충분히 어두우면 내용
                dark = True
                break
        if dark:
            last_dark = ry
            blank_run = 0
            started = True
        elif started:
            blank_run += 1
            if blank_run >= gap_stop_px:   # 내용 뒤 큰 여백 → 여기서 끊음
                break
    return last_dark / scale


def main():
    d = fitz.open(PDF)
    entries = []      # 각 문제 = {num, page(1-based), pdf_page(0-based), column, bbox}
    for pno in range(d.page_count):
        page = d[pno]
        badges = find_badges(page)
        labels = find_labels(page, badges)
        if not labels:
            continue
        page_h = page.rect.height
        pix = page.get_pixmap(dpi=TRIM_DPI)   # 트리밍용
        for col in ("L", "R"):
            col_labels = sorted([l for l in labels if l[1] == col], key=lambda t: t[2])
            x_range = LEFT_X if col == "L" else RIGHT_X
            for i, (num, _, eff, _label_y0) in enumerate(col_labels):
                y_top = max(0, eff - TOP_PAD)
                # 아래 한계 = 같은 단 다음 문제 시작(뱃지 포함 위치), 없으면 단 바닥
                y_limit = col_labels[i+1][2] - 4 if i+1 < len(col_labels) else COL_BOTTOM
                y_bot = min(content_bottom(pix, x_range, y_top, y_limit, page_h) + BOT_PAD, y_limit)
                entries.append({
                    "num": num,
                    "page": pno + 1,        # 사용자가 입력할 1-based 페이지
                    "pdf_page": pno,        # fitz 렌더용 0-based
                    "column": col,
                    "bbox": [round(x_range[0], 1), round(y_top, 1),
                             round(x_range[1], 1), round(y_bot, 1)],
                })
    # 읽기 순서(페이지 -> 좌단 -> 우단 -> 위에서 아래)로 정렬
    entries.sort(key=lambda e: (e["pdf_page"], e["column"] == "R", e["bbox"][1]))
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"pdf": os.path.basename(PDF), "problems": entries},
                  f, ensure_ascii=False, indent=2)

    # 번호 중복(같은 번호가 여러 페이지) 여부 알림
    from collections import Counter
    dup = [n for n, c in Counter(e["num"] for e in entries).items() if c > 1]

    print(f"색인 완료: 문제 {len(entries)}개 -> {OUT_JSON}\n")
    print("=== 페이지별 문제 목록 (입력은 '페이지:번호' 형식) ===")
    cur = None
    for e in sorted(entries, key=lambda e: (e["page"], e["num"])):
        if e["page"] != cur:
            cur = e["page"]
            print(f"\n [{cur}페이지]  ", end="")
        print(e["num"], end=" ")
    print("\n")
    if dup:
        print(f"※ 번호 {dup} 는 여러 페이지에 있습니다 → 반드시 '페이지:번호'로 지정하세요.")
    else:
        print("※ 번호가 모두 유일합니다 → 번호만 입력해도 되고, '페이지:번호'로 명확히 해도 됩니다.")


if __name__ == "__main__":
    main()
