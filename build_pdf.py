# -*- coding: utf-8 -*-
"""
problems_index.json 을 이용해, 원하는 문제 번호만 골라
학원 양식(수.hwp, template.py)에 맞춘 2단 PDF로 조립한다. (build_docx 와 같은 모양)

입력은 '페이지:번호' 형식 (헷갈림 방지):
    python build_pdf.py 2:5 2:7 3:1-4       # 2페이지 5·7번, 3페이지 1~4번
    python build_pdf.py 1 5 9 16 23         # 번호가 유일하면 번호만도 가능
    python build_pdf.py 2:5 3:1-4 -o my_set.pdf
    python build_pdf.py 1 5 9 --cols 1      # 1단으로

각 문제는 원본에서 고해상도로 잘라 좌단 → 우단 → 다음 페이지 순서로 배치한다.
"""
import fitz, os
import selector
import template as T

HERE = os.path.dirname(os.path.abspath(__file__))
MM = T.MM

GAP = 14                            # 문제 사이 간격(pt)
LABEL_H = 16                        # [쪽:번호] 라벨 줄 높이(pt)


def korean_font():
    """한글이 되는 글꼴. 윈도우 맑은 고딕, 없으면 PyMuPDF 내장 CJK 글꼴."""
    if os.path.exists(T.KOREAN_FONT_FILE):
        return fitz.Font(fontfile=T.KOREAN_FONT_FILE)
    return fitz.Font("korea")


class Writer:
    """학원 양식 페이지를 만들고, 문제 블록을 단 단위로 흘려 넣는다."""

    def __init__(self, title, cols, start_page=0):
        self.doc = fitz.open()
        self.start_page = start_page          # 이어 붙일 때: 앞 파일의 쪽 수 (쪽 번호를 이어서 매김)
        self.font = korean_font()
        self.title = title
        self.cols = cols
        self.col_w = T.col_width_mm(cols) * MM
        self.top = T.BODY_TOP_MM * MM
        self.bot = T.BODY_BOT_MM * MM
        self.page = None
        self.col = 0
        self.y = self.top
        self.new_page()

    def text(self, page, x, y, s, size, color=(0, 0, 0), align="left"):
        """(x, y)=기준선 위치. align: left / right / center"""
        w = self.font.text_length(s, fontsize=size)
        if align == "right":
            x -= w
        elif align == "center":
            x -= w / 2
        tw = fitz.TextWriter(page.rect, color=color)
        tw.append((x, y), s, font=self.font, fontsize=size)
        tw.write_text(page)

    def new_page(self):
        W, H = T.PAGE_W_MM * MM, T.PAGE_H_MM * MM
        page = self.doc.new_page(width=W, height=H)
        pno = str(self.start_page + self.doc.page_count)
        x0, x1 = T.MARGIN_X_MM * MM, (T.PAGE_W_MM - T.MARGIN_X_MM) * MM
        bar = T.BAR_PT

        # 머리말: 왼쪽 파일 이름, 오른쪽 페이지 번호, 아래 굵은 선
        base = (T.HEADER_BAR_Y_MM - 2.0) * MM
        self.text(page, x0, base, self.title, T.HF_FONT_PT)
        self.text(page, x1, base, pno, T.HF_FONT_PT, align="right")
        hy = T.HEADER_BAR_Y_MM * MM
        page.draw_rect(fitz.Rect(x0, hy, x1, hy + bar), color=None, fill=(0, 0, 0))

        # 꼬리말: 굵은 선, 그 아래 가운데 페이지 번호
        fy = T.FOOTER_BAR_Y_MM * MM
        page.draw_rect(fitz.Rect(x0, fy, x1, fy + bar), color=None, fill=(0, 0, 0))
        self.text(page, W / 2, fy + bar + T.HF_FONT_PT + 1, pno, T.HF_FONT_PT, align="center")

        # 단 사이 가운데 구분선
        for c in range(1, self.cols):
            sx = x0 + c * self.col_w + (c - 0.5) * T.COL_GAP_MM * MM
            page.draw_line((sx, self.top), (sx, self.bot), color=(0, 0, 0), width=0.5)

        self.page, self.col, self.y, self.row = page, 0, self.top, 0

    def next_column(self):
        self.row = 0
        if self.col + 1 < self.cols:
            self.col += 1
            self.y = self.top
        else:
            self.new_page()

    def col_x(self):
        return T.MARGIN_X_MM * MM + self.col * (self.col_w + T.COL_GAP_MM * MM)

    def place_slot(self, pix, per_col):
        """칸 배치: 문제를 지금 칸의 맨 위에 붙인다. 긴 문제는 칸을 여러 개 차지하고,
        지금 단에 남은 칸이 모자라면 다음 단(→ 다음 쪽)으로 넘긴다. 아래는 빈 풀이 공간."""
        w_mm, h_mm = T.fit_size_mm(pix.width / T.RENDER_DPI * 25.4, pix.height / T.RENDER_DPI * 25.4,
                                   self.cols, per_col)
        k = T.slots_for(h_mm, per_col)
        if self.row + k > per_col:
            self.next_column()
        x = self.col_x()
        y = self.top + self.row * T.slot_height_mm(per_col) * MM
        self.page.insert_image(fitz.Rect(x, y, x + w_mm * MM, y + h_mm * MM), stream=pix.tobytes("png"))
        self.row += k

    def place(self, pix, clip, label):
        # 원본 크기(pt) 유지하되 단 폭을 넘으면 축소, 한 단보다 길면 높이에 맞춰 축소
        label_h = LABEL_H if label else 0
        scale = min(1.0, self.col_w / clip.width,
                    (self.bot - self.top - label_h) / clip.height)
        draw_w, draw_h = clip.width * scale, clip.height * scale
        if self.y + label_h + draw_h > self.bot and self.y > self.top:
            self.next_column()

        x = self.col_x()
        if label:
            self.text(self.page, x, self.y + 11, label, T.LABEL_FONT_PT,
                      color=tuple(c / 255 for c in T.LABEL_COLOR))
            self.y += label_h
        self.page.insert_image(fitz.Rect(x, self.y, x + draw_w, self.y + draw_h),
                               stream=pix.tobytes("png"))   # PNG 로 넣어야 파일이 작다
        self.y += draw_h + GAP


def build(items, out_path, cols=T.COLS, per_col=T.PER_COL):
    """items: [{"pix": 잘라 둔 문제(fitz.Pixmap, RENDER_DPI), "label": "[ 2:5 ]"}] → out_path(.pdf) 저장.
    반환: 쪽 수"""
    w = Writer(os.path.basename(out_path), cols)   # 머리말에 파일 이름 (수.hwp 와 동일)
    place_items(w, items, per_col)
    w.doc.save(out_path, garbage=3, deflate=True)
    return w.doc.page_count


def place_items(w, items, per_col):
    for it in items:
        pix = it["pix"]
        if per_col:
            w.place_slot(pix, per_col)
        else:
            clip = fitz.Rect(0, 0, pix.width * 72 / T.RENDER_DPI, pix.height * 72 / T.RENDER_DPI)   # 원본 크기(pt)
            w.place(pix, clip, it.get("label") if T.SHOW_LABEL else None)
    w.doc.subset_fonts()     # 맑은 고딕 전체(수 MB) 대신 실제로 쓴 글자만 포함


def append(items, path, cols=T.COLS, per_col=T.PER_COL):
    """이미 만든 .pdf 끝에 새 쪽부터 문제를 이어 붙여 같은 파일에 저장 (쪽 번호도 이어서)."""
    src = fitz.open(path)
    w = Writer(os.path.basename(path), cols, start_page=src.page_count)
    place_items(w, items, per_col)
    src.insert_pdf(w.doc)
    tmp = path + ".tmp-append"
    src.save(tmp, garbage=3, deflate=True)
    src.close()
    os.replace(tmp, path)
    return w.doc.page_count


def main():
    args = selector.cli_args("selected_problems.pdf")
    items = selector.cli_items(args.numbers)
    build(items, os.path.join(HERE, args.out), args.cols, args.per_col)
    selector.cli_report(args, items)


if __name__ == "__main__":
    main()
