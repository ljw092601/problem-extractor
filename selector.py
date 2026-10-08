# -*- coding: utf-8 -*-
"""
problems_index.json 로드 + '페이지:번호' 입력 토큰 해석 (build_pdf / build_docx 공용).

입력 토큰 문법:
    5        번호 5 (유일할 때만; 여러 페이지에 있으면 페이지 지정 요구)
    2:5      2페이지의 5번
    2:5-8    2페이지의 5,6,7,8번
    5-8      번호 5~8 (각 번호가 유일할 때)
    혼용 예: 1:5 2:3-4 20
"""
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "problems_index.json")


def load_index():
    with open(INDEX, encoding="utf-8") as f:
        data = json.load(f)
    return data["pdf"], data["problems"]


def _expand(body):
    """'5' -> [5],  '5-8' -> [5,6,7,8].  '8-5' 처럼 거꾸로 쓰면 ValueError"""
    if "-" in body:
        a, b = body.split("-")
        a, b = int(a), int(b)
        if a > b:
            raise ValueError("역순 범위")
        return list(range(a, b + 1))
    return [int(body)]


def resolve(tokens, entries):
    """토큰 목록 -> (선택된 entry 목록, 오류 메시지 목록). 입력 순서 유지, 중복 제거."""
    by_num, by_pn = {}, {}
    for e in entries:
        for n in range(e["num"], e.get("num_end", e["num"]) + 1):   # 묶음 문제는 범위 안 모든 번호로 찾힘
            by_num.setdefault(n, []).append(e)
            by_pn[(e["page"], n)] = e

    result, errors = [], []
    for tok in tokens:
        page, body = None, tok
        try:
            if ":" in tok:
                ps, body = tok.split(":", 1)
                page = int(ps)
            nums = _expand(body)
        except ValueError:
            errors.append(f"'{tok}' 형식 오류 (예: 5, 2:5, 2:5-8)"); continue
        for n in nums:
            if page is not None:
                e = by_pn.get((page, n))
                if e is None:
                    errors.append(f"{page}:{n} 없음")
                else:
                    result.append(e)
            else:
                lst = by_num.get(n, [])
                if not lst:
                    errors.append(f"{n} 없음")
                elif len(lst) > 1:
                    pages = ", ".join(str(x["page"]) for x in lst)
                    errors.append(f"{n}은 여러 페이지({pages})에 있음 → '{lst[0]['page']}:{n}' 처럼 페이지 지정")
                else:
                    result.append(lst[0])

    seen, out = set(), []
    for e in result:
        k = (e["page"], e["num"])
        if k not in seen:
            seen.add(k); out.append(e)
    return out, errors


# ---- 잘라내기 + 명령줄 공용 (build_docx / build_pdf / build_hwpx) --------------------

def num_text(e):
    """'5' 또는 묶음이면 '125~128'"""
    return f"{e['num']}~{e['num_end']}" if e.get("num_end") and e["num_end"] != e["num"] else str(e["num"])


def crop_item(doc, e):
    """좌표 한 개 → 빌더에 넘길 항목 {"pix": 고해상도 크롭, "label": "[ 쪽:번호 ]"}. doc: 열린 fitz 문서"""
    import fitz
    import template as T
    from core.pdfpage import ready_page
    clips = [(e["pdf_page"], fitz.Rect(*e["bbox"]))] + [(q["pdf_page"], fitz.Rect(*q["bbox"]))
                                                        for q in e.get("parts", [])]
    for pno, _ in clips:                     # 그리기가 깨지는 교재는 쪽 내용을 먼저 정리 (core/pdfpage.py)
        ready_page(doc, pno, e.get("clean"))
    if len(clips) == 1:
        pix = doc[e["pdf_page"]].get_pixmap(dpi=T.RENDER_DPI, clip=clips[0][1])
    else:                                    # 다음 단·쪽으로 이어지는 문제: 조각들을 위아래로 이어 붙인다
        tmp = fitz.open()
        page = tmp.new_page(width=max(r.width for _, r in clips), height=sum(r.height for _, r in clips))
        y = 0
        for pno, r in clips:
            page.show_pdf_page(fitz.Rect(0, y, r.width, y + r.height), doc, pno, clip=r)
            y += r.height
        pix = page.get_pixmap(dpi=T.RENDER_DPI)
        tmp.close()
    r0 = fitz.Rect(*e["bbox"])
    rel_w = r0.width / doc[e["pdf_page"]].rect.width        # 원본 쪽 폭 대비 문제 폭 (1단 편집 교재 판단용)
    return {"pix": pix, "label": f"[ {e['page']}:{num_text(e)} ]", "rel_w": rel_w}


WIDE_REL_W = 0.6


def auto_cols(items):
    """담은 문제의 절반 이상이 쪽 폭의 60%보다 넓으면(1단 편집 교재) 1단, 아니면 2단."""
    wide = sum(1 for it in items if it.get("rel_w", 0) > WIDE_REL_W)
    return 1 if items and wide * 2 >= len(items) else 2


def cli_args(default_out):
    import argparse
    import template as T
    ap = argparse.ArgumentParser()
    ap.add_argument("numbers", nargs="+", help="페이지:번호 (예: 2:5 3:1-4) 또는 유일한 번호 (예: 1 5 9)")
    ap.add_argument("-o", "--out", default=default_out, help="출력 파일명")
    ap.add_argument("--cols", type=int, default=T.COLS, help=f"단 수 (기본 {T.COLS})")
    ap.add_argument("--per-col", type=int, default=T.PER_COL,
                    help=f"한 단에 넣을 문제 수 (기본 {T.PER_COL}, 0이면 이어 붙임)")
    return ap.parse_args()


def cli_items(tokens):
    """이 폴더의 problems_index.json + 원본 PDF 에서 입력한 문제들을 잘라 온다."""
    import fitz
    pdf_name, entries = load_index()
    src = fitz.open(os.path.join(HERE, pdf_name))
    chosen, errors = resolve(tokens, entries)
    for msg in errors:
        print("  건너뜀:", msg)
    if not chosen:
        raise SystemExit("담을 문제가 없습니다. 입력을 확인하세요 (예: 2:5 3:1-4).")
    return [crop_item(src, e) for e in chosen]


def cli_report(args, items):
    print(f"완료: {len(items)}문제 -> {args.out}  ({args.cols}단, 단마다 {args.per_col or '이어 붙임'}문제)")
    print("  담김:", ", ".join(it["label"].strip("[] ") for it in items))
