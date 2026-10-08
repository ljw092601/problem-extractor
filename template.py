# -*- coding: utf-8 -*-
"""
학원 양식(수.hwp) 규격 — build_docx / build_pdf 공용.

수.hwp 에서 추출한 값 (단위 mm):
  - A4, 좌우 여백 12, 위아래 여백 8, 머리말·꼬리말 영역 각 10 → 본문 18 ~ 279
  - 2단, 단 간격 8, 가운데 실선 구분선
  - 머리말: 왼쪽 파일 이름, 오른쪽 페이지 번호(9pt), 그 아래 굵은 선(두께 약 1.06 = 3pt)
  - 꼬리말: 굵은 선, 그 아래 가운데 페이지 번호(9pt)
"""
import os

MM = 72 / 25.4                     # mm -> pt

PAGE_W_MM, PAGE_H_MM = 210.0, 297.0
MARGIN_X_MM = 12.0                 # 좌우 여백
MARGIN_Y_MM = 8.0                  # 위아래 여백 (종이 끝 ~ 머리말/꼬리말)
HEADER_H_MM = 10.0                 # 머리말·꼬리말 영역 높이
BODY_TOP_MM = MARGIN_Y_MM + HEADER_H_MM                 # 18
BODY_BOT_MM = PAGE_H_MM - MARGIN_Y_MM - HEADER_H_MM     # 279
BODY_W_MM = PAGE_W_MM - 2 * MARGIN_X_MM                 # 186
COL_GAP_MM = 8.0
COLS = 2

BAR_PT = 3.0                       # 굵은 선 두께 (1.06mm)
HEADER_BAR_Y_MM = 12.8             # 머리말 굵은 선 위쪽 y
FOOTER_BAR_Y_MM = 284.8            # 꼬리말 굵은 선 위쪽 y
HF_FONT_PT = 9                     # 머리말·꼬리말 글자 크기
HF_FONT_NAME = "맑은 고딕"          # 원본은 함초롬돋움(한글 설치 PC에만 있음) → 윈도우 기본 글꼴로 대체

LABEL_FONT_PT = 10                 # 문제 위 [쪽:번호] 라벨
LABEL_COLOR = (0xC0, 0x20, 0x20)
SHOW_LABEL = False                 # 문제 위 [쪽:번호] 라벨 (학원 양식엔 없음 → 끔)
RENDER_DPI = 300                   # 원본 크롭 해상도(인쇄 품질)

# PDF 에서 한글을 쓰기 위한 글꼴 파일 (윈도우 기본). 없으면 PyMuPDF 내장 CJK 글꼴 사용
KOREAN_FONT_FILE = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "malgun.ttf")


PER_COL = 2                        # 한 단에 넣을 문제 수 → 2단이면 한 쪽에 4문제. 0 이면 간격 없이 이어 붙임
SLOT_PAD_MM = 4                    # 칸 안에서 다음 문제 자리를 위해 남기는 여유

BODY_H_MM = BODY_BOT_MM - BODY_TOP_MM


def col_width_mm(cols=COLS):
    return (BODY_W_MM - (cols - 1) * COL_GAP_MM) / cols


def slot_height_mm(per_col=PER_COL):
    """문제 한 칸의 높이. 단 높이를 per_col 개로 똑같이 나눈다."""
    return BODY_H_MM / per_col if per_col else BODY_H_MM


def fit_size_mm(native_w_mm, native_h_mm, cols=COLS, per_col=PER_COL):
    """문제 이미지 크기: 단 폭에 맞추되 원본보다 키우지 않는다.
    칸 하나보다 긴 문제는 칸을 여러 개(최대 한 단 전체) 차지하고, 한 단보다 길면 높이에 맞춰 줄인다."""
    max_h = BODY_H_MM - 2 * SLOT_PAD_MM if per_col else BODY_H_MM - 12
    w = min(col_width_mm(cols), native_w_mm)
    h = native_h_mm * w / native_w_mm
    if h > max_h:
        w, h = max_h * native_w_mm / native_h_mm, max_h
    return w, h


def slots_for(h_mm, per_col=PER_COL):
    """이 높이의 문제가 차지하는 칸 수 (1 ~ per_col)."""
    if not per_col:
        return 1
    slot = slot_height_mm(per_col)
    k = 1
    while k < per_col and h_mm > k * slot - 2 * SLOT_PAD_MM:
        k += 1
    return k


BODY_FONT_PT = 10                  # 본문 글자 (수.hwp 와 동일)
LINE_PT = 16                       # 본문 한 줄 높이 = 10pt × 줄 간격 160%
LINE_MM = LINE_PT / MM


def blank_lines(space_mm):
    """space_mm 를 넘지 않는 빈 줄 수 (문제 사이 간격을 엔터로 채울 때)."""
    return max(0, int(space_mm // LINE_MM))

