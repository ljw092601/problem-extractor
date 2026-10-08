# -*- coding: utf-8 -*-
"""
problems_index.json 을 이용해, 원하는 문제 번호만 골라
학원 양식(수.hwp, template.py)에 맞춘 2단 한글(.hwpx) 문서로 조립한다. (build_docx 와 같은 모양)

입력은 '페이지:번호' 형식 (헷갈림 방지):
    python build_hwpx.py 2:5 2:7 3:1-4 -o 오답노트.hwpx
    python build_hwpx.py 1 5 9 --cols 1       # 1단으로

HWPX = 한글 2014 이후 표준 형식(ZIP+XML). 한글이 설치되지 않은 PC에서도 만들 수 있고, 한글에서 바로 열린다.
문서 뼈대·그림 삽입은 python-hwpx 라이브러리로, 단·머리말·꼬리말은 수.hwp 와 같은 방식으로 직접 넣는다.
  - 머리말: 파일 이름 + (오른쪽 탭) 쪽 번호, 문단 아래 굵은 선
  - 꼬리말: 문단 위 굵은 선 + 가운데 쪽 번호
  - 쪽 번호는 수.hwp 와 같이 자동 번호(autoNum PAGE) 컨트롤
"""
import os, io, zipfile
from xml.sax.saxutils import escape
from hwpx import HwpxDocument
import selector
import template as T

HERE = os.path.dirname(os.path.abspath(__file__))

HWPUNIT_PER_MM = 7200 / 25.4
HWP_PIC_EXTRA_MM = 1.5         # 그림 줄에 붙는 여분 높이
HWP_EXTRA_LINES = 2            # 한글에서 실제로 보니 칸 간격이 좁음 → 위 칸 문제 아래에 빈 줄 추가 (단의 마지막 칸 제외: 넘치면 다음 단으로 밀림)
BAR_WIDTH = "1.0 mm"             # 한글 선 굵기 목록 중 수.hwp 의 굵은 선(약 1.06mm)에 가장 가까운 값


def hu(mm):
    return int(round(mm * HWPUNIT_PER_MM))


def header_footer_xml(kind, para_id, char_id, title=None):
    """머리말/꼬리말 컨트롤 XML. kind: 'header' | 'footer'"""
    page_num = ('<hp:run charPrIDRef="{c}"><hp:ctrl><hp:autoNum num="1" numType="PAGE">'
                '<hp:autoNumFormat type="DIGIT" userChar="" prefixChar="" suffixChar="" supscript="0"/>'
                '</hp:autoNum></hp:ctrl></hp:run>').format(c=char_id)
    if kind == "header":
        text = (f'<hp:run charPrIDRef="{char_id}"><hp:t>{escape(title)}'
                f'<hp:tab width="{hu(T.BODY_W_MM) // 2}" leader="0" type="2"/></hp:t></hp:run>')
        runs, valign, uid = text + page_num, "TOP", 1
    else:
        runs, valign, uid = page_num, "BOTTOM", 2
    return (f'<hp:ctrl><hp:{kind} id="{uid}" applyPageType="BOTH">'
            f'<hp:subList id="" textDirection="HORIZONTAL" lineWrap="BREAK" vertAlign="{valign}" '
            f'linkListIDRef="0" linkListNextIDRef="0" textWidth="{hu(T.BODY_W_MM)}" '
            f'textHeight="{hu(T.HEADER_H_MM)}" hasTextRef="0" hasNumRef="1">'
            f'<hp:p id="{uid}" paraPrIDRef="{para_id}" styleIDRef="0" pageBreak="0" columnBreak="0" merged="0">'
            f'{runs}</hp:p></hp:subList></hp:{kind}></hp:ctrl>')


def columns_xml(cols):
    line = ('<hp:colLine type="SOLID" width="0.12 mm" color="#000000"/>' if cols > 1 else "")
    return (f'<hp:ctrl><hp:colPr id="" type="NEWSPAPER" layout="LEFT" colCount="{cols}" '
            f'sameSz="1" sameGap="{hu(T.COL_GAP_MM)}">{line}</hp:colPr></hp:ctrl>')


def patch_section(xml, cols, header, footer):
    """첫 문단의 단 설정(colPr 1단)을 양식의 단 설정으로 바꾸고, 그 뒤에 머리말·꼬리말을 붙인다."""
    start = xml.index("<hp:ctrl><hp:colPr")
    end = xml.index("</hp:ctrl>", start) + len("</hp:ctrl>")
    return xml[:start] + columns_xml(cols) + header + footer + xml[end:]


def rezip(data, replace):
    """HWPX(zip)의 일부 파일만 바꿔 다시 묶는다. mimetype 은 맨 앞·무압축 유지."""
    src = zipfile.ZipFile(io.BytesIO(data))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as dst:
        for info in src.infolist():
            body = replace.get(info.filename, src.read(info.filename))
            dst.writestr(info, body, compress_type=info.compress_type)
    return out.getvalue()


def build(items, out_path, cols=T.COLS, per_col=T.PER_COL):
    """items: [{"pix": 잘라 둔 문제(fitz.Pixmap, RENDER_DPI), "label": ...}] → out_path(.hwpx) 저장."""
    doc = HwpxDocument.new()
    doc.page.setup(width_mm=T.PAGE_W_MM, height_mm=T.PAGE_H_MM,
                   margin_left_mm=T.MARGIN_X_MM, margin_right_mm=T.MARGIN_X_MM,
                   margin_top_mm=T.MARGIN_Y_MM, margin_bottom_mm=T.MARGIN_Y_MM,
                   header_margin_mm=T.HEADER_H_MM, footer_margin_mm=T.HEADER_H_MM)

    # 머리말·꼬리말용 글자/문단 모양 (header.xml 에 등록하고 id 를 받는다)
    head = doc._root.headers[0]
    char_hf = doc.styles.ensure_run(size=T.HF_FONT_PT)
    tab_right = head.ensure_tab_definition(
        tab_stops=[{"pos": hu(T.BODY_W_MM), "type": "RIGHT", "leader": "NONE"}])

    def bar_border(side):
        return {"borderFillIDRef": head.ensure_border_fill(border_color="#000000", border_width=BAR_WIDTH,
                                                           active_borders=(side,)),
                "offsetLeft": "0", "offsetRight": "0", "offsetTop": "0", "offsetBottom": "0",
                "connect": "0", "ignoreMargin": "1"}

    para_header = head.ensure_paragraph_format(base_para_pr_id="0", alignment="LEFT",
                                               line_spacing_percent=100, border=bar_border("bottom"),
                                               tab_pr_id_ref=tab_right)
    para_footer = head.ensure_paragraph_format(base_para_pr_id="0", alignment="CENTER",
                                               line_spacing_percent=100, border=bar_border("top"))
    add_items(doc, items, cols, per_col, first_line_used=True)   # 맨 앞 구역 설정 문단이 한 줄 차지

    buf = io.BytesIO()
    doc.save_to_stream(buf)
    data = buf.getvalue()

    section = zipfile.ZipFile(io.BytesIO(data)).read("Contents/section0.xml").decode("utf-8")
    section = patch_section(
        section, cols,
        header_footer_xml("header", para_header, char_hf, title=os.path.basename(out_path)),
        header_footer_xml("footer", para_footer, char_hf))
    data = rezip(data, {"Contents/section0.xml": section.encode("utf-8")})

    HwpxDocument.open(io.BytesIO(data))     # 다시 열어 구조가 깨지지 않았는지 확인
    with open(out_path, "wb") as f:
        f.write(data)


def add_items(doc, items, cols, per_col, first_line_used=False, first_attrs=None):
    """문서 끝에 문제 그림(+칸 맞춤 빈 줄)을 차례로 넣는다. first_attrs: 첫 그림 문단에 붙일 속성(쪽 나눔 등)."""
    head = doc._root.headers[0]

    def para_after(space_hu):
        """그림 문단 모양: 아래 간격(HWPUNIT)만 다르다."""
        return head.ensure_paragraph_format(base_para_pr_id="0", alignment="LEFT",
                                            line_spacing_percent=100,
                                            margins={"prev": 0, "next": max(0, int(space_hu))})

    para_flow = para_after(1000)          # 이어 붙이기: 문제 사이 10pt
    para_pic = para_after(0)              # 칸 배치: 간격은 빈 줄로 채움
    slot_h_mm = T.slot_height_mm(per_col)
    slot_row = 0                                              # 지금 단에서 다음 문제가 들어갈 칸

    for i, it in enumerate(items):
        pix = it["pix"]
        attrs = (first_attrs or {}) if i == 0 else {}
        w_mm, h_mm = T.fit_size_mm(pix.width / T.RENDER_DPI * 25.4, pix.height / T.RENDER_DPI * 25.4,
                                   cols, per_col)
        if not per_col:
            doc.add_picture(pix.tobytes("png"), "png", width_mm=w_mm, height_mm=h_mm, para_pr_id_ref=para_flow,
                            **attrs)
            continue

        # 칸 배치: 문제 아래를 빈 줄(엔터)로 채워 칸 높이를 맞춘다. 선생님이 빈 줄을 지우거나
        # 엔터를 쳐서 간격을 직접 조정할 수 있다. 빈 줄은 기본 문단 모양(10pt, 줄 간격 160% = 16pt).
        # 빈 줄 수는 칸을 넘지 않게 내림 → 다음 문제는 자기 칸 맨 위(또는 다음 단)에서 시작
        doc.add_picture(pix.tobytes("png"), "png", width_mm=w_mm, height_mm=h_mm, para_pr_id_ref=para_pic,
                        **attrs)
        k = T.slots_for(h_mm, per_col)                       # 긴 문제는 칸을 여러 개 차지
        space = k * slot_h_mm - h_mm - (T.LINE_MM if i == 0 and first_line_used else 0)
        row = slot_row % per_col
        slot_row = 0 if row + k >= per_col else row + k       # 이 문제 뒤에 단이 끝나면 다음 단 맨 위부터
        extra = 0 if slot_row == 0 else HWP_EXTRA_LINES       # 단의 마지막 칸엔 여분 줄을 넣지 않음
        for _ in range(T.blank_lines(space - HWP_PIC_EXTRA_MM) + extra):
            doc.add_paragraph("")


def append(items, path, cols=T.COLS, per_col=T.PER_COL):
    """이미 만든 .hwpx 끝에 새 쪽부터 문제를 이어 붙여 같은 파일에 저장.
    첫 문제 문단에 쪽 나눔 + 단 설정(다단 설정 나누기)을 넣는다. 머리말·꼬리말·쪽 번호는 그대로 이어진다.
    선생님이 한글에서 고친 내용은 그대로 둔다."""
    doc = HwpxDocument.open(path)
    add_items(doc, items, cols, per_col, first_attrs={"pageBreak": "1"})
    buf = io.BytesIO()
    doc.save_to_stream(buf)
    data = buf.getvalue()

    z = zipfile.ZipFile(io.BytesIO(data))
    last = sorted((n for n in z.namelist() if n.startswith("Contents/section") and n.endswith(".xml")),
                  key=lambda n: int("".join(ch for ch in n if ch.isdigit()) or 0))[-1]
    xml = z.read(last).decode("utf-8")
    at = xml.rfind('pageBreak="1"')                       # 방금 넣은 첫 문제 문단
    run = xml.index("<hp:run", at)
    run_body = xml.index(">", run) + 1                    # 그 문단 첫 run 안 맨 앞에 단 설정
    xml = xml[:run_body] + columns_xml(cols) + xml[run_body:]
    data = rezip(data, {last: xml.encode("utf-8")})

    HwpxDocument.open(io.BytesIO(data))     # 다시 열어 구조가 깨지지 않았는지 확인
    tmp = path + ".tmp-append"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def main():
    args = selector.cli_args("selected_problems.hwpx")
    items = selector.cli_items(args.numbers)
    build(items, os.path.join(HERE, args.out), args.cols, args.per_col)
    selector.cli_report(args, items)


if __name__ == "__main__":
    main()
