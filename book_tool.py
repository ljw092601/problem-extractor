# -*- coding: utf-8 -*-
"""
교재 등록 작업 도구 (관리자 / Claude 에이전트용). 결과는 로컬 작업 폴더에만 쓴다 — 등록(관리 기록 쓰기)은 admin.py 로 따로.

    python book_tool.py info    <pdf>                              쪽 수, 크기, 글자 정보 유무, PDF 목차
    python book_tool.py render  <pdf> --pages 21,22 --out D [--dpi 70]
                                  쪽 이미지 + 50pt 간격 좌표 눈금(빨간 숫자 = pt). 이미지를 보고 단 경계·번호 위치를 읽는다
    python book_tool.py probe   <pdf> --pages 21,22 [--ocr]     숫자로 된 글자 조각의 위치(x,y)·크기 목록
    python book_tool.py extract <pdf> <layout.json> --out D [--pages 21-30,40]
                                  좌표 추출 → D/problems.json, D/report.txt, D/sheets/*.png (모아보기)
    python book_tool.py ocrtext <pdf> --pages 21 [--lang ko]    쪽 전체 OCR 글자 (단원 제목 찾기 등)
    python book_tool.py units   <problems.json> <units.json>      단원 나누기 미리보기 (단원별 문제 수·번호 범위)

레이아웃 설정 형식은 core/extract.py 맨 위 설명 참고.
"""
import argparse
import json
import os
import re
import sys

import fitz

from core import extract as X


def parse_pages(s):
    out = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def cmd_info(a):
    d = fitz.open(a.pdf)
    n = d.page_count
    probe = sorted({min(n - 1, k) for k in (2, n // 4, n // 2, 3 * n // 4)})
    chars = [len(d[i].get_text().strip()) for i in probe]
    print(f"쪽 {n}, 첫 쪽 크기 {d[0].rect.width:.0f}x{d[0].rect.height:.0f}pt")
    print(f"글자 수 표본 {dict(zip([p + 1 for p in probe], chars))} → {'텍스트 PDF' if max(chars) > 150 else '스캔본(OCR 필요)'}")
    toc = d.get_toc()
    print(f"PDF 목차 {len(toc)}개")
    for lv, t, p in toc[:80]:
        print(f"  {'  ' * (lv - 1)}{t} → {p}쪽")


def cmd_render(a):
    d = fitz.open(a.pdf)
    os.makedirs(a.out, exist_ok=True)
    for p in parse_pages(a.pages):
        page = d[p - 1]
        tmp = fitz.open()
        pg = tmp.new_page(width=page.rect.width, height=page.rect.height)
        pg.show_pdf_page(pg.rect, d, p - 1)
        W, H = page.rect.width, page.rect.height
        for x in range(0, int(W) + 1, 50):
            pg.draw_line((x, 0), (x, H), color=(1, 0, 0), width=0.3)
            pg.insert_text((x + 1, 9), str(x), fontsize=7, color=(1, 0, 0))
        for y in range(0, int(H) + 1, 50):
            pg.draw_line((0, y), (W, y), color=(1, 0, 0), width=0.3)
            pg.insert_text((1, y - 1), str(y), fontsize=7, color=(1, 0, 0))
        path = os.path.join(a.out, f"p{p:04d}.png")
        pg.get_pixmap(dpi=a.dpi).save(path)
        print(path)


def cmd_probe(a):
    d = fitz.open(a.pdf)
    cfg = {"source": "ocr" if a.ocr else "text", "ocr_dpi": [150, 200], "body": None}
    for p in parse_pages(a.pages):
        page = d[p - 1]
        toks = X._ocr_tokens(page, cfg) if a.ocr else list(X._text_tokens(page))
        print(f"--- {p}쪽 ({page.rect.width:.0f}x{page.rect.height:.0f})")
        for text, bbox, size in sorted(toks, key=lambda t: (round(t[1][0] / 20), t[1][1])):
            if re.search(r"\d", text) and len(text) <= 8:
                print(f"  x{bbox[0]:6.1f} y{bbox[1]:6.1f}  크기{size:5.1f}  {text!r}")


def cmd_extract(a):
    cfg = X.load_layout(a.layout)
    only = parse_pages(a.pages) if a.pages else None

    def prog(k, n, page, found):
        if k % 20 == 0 or k == n:
            print(f"  {k}/{n}쪽 처리 (현재 {page}쪽, 번호 {found}개)", flush=True)

    problems, rep = X.extract(a.pdf, cfg, only, prog)
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "problems.json"), "w", encoding="utf-8") as f:
        json.dump({"pdf": os.path.basename(a.pdf), "problems": problems}, f, ensure_ascii=False, indent=1)
    txt = X.report_text(rep)
    with open(os.path.join(a.out, "report.txt"), "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)
    if not a.no_sheets:
        sheets = X.contact_sheets(a.pdf, problems, os.path.join(a.out, "sheets"))
        print(f"모아보기 {len(sheets)}장: {os.path.join(a.out, 'sheets')}")


def cmd_ocrtext(a):
    from core import winocr
    d = fitz.open(a.pdf)
    for p in parse_pages(a.pages):
        words = winocr.ocr_pixmap(d[p - 1].get_pixmap(dpi=200), a.lang)
        sc = 72 / 200
        lines = {}
        for w, x0, y0, x1, y1 in words:
            lines.setdefault(round(y0 * sc / 6), []).append((x0 * sc, w))
        print(f"--- {p}쪽")
        for k in sorted(lines):
            ws = sorted(lines[k])
            print(f"  y{k * 6:4d} x{ws[0][0]:5.0f}: " + " ".join(w for _, w in ws))


def cmd_units(a):
    from core import books
    with open(a.problems, encoding="utf-8") as f:
        probs = json.load(f)["problems"]
    with open(a.units, encoding="utf-8") as f:
        units = json.load(f)
    books._check_units(units)
    books.assign_units(probs, units)
    for g in books.unit_groups({"problems": probs, "units": units}):
        ps = g["problems"]
        print(f"  [{g.get('group') or ''}] {g['title']}: {len(ps)}문제 "
              f"({ps[0]['page']}쪽 {ps[0]['num']}번 ~ {ps[-1]['page']}쪽 {ps[-1]['num']}번)")
    empty = [u["title"] for u in units if not any(p.get("unit") == u["id"] for p in probs)]
    if empty:
        print("  ⚠ 문제가 하나도 없는 단원:", empty)


def main():
    ap = argparse.ArgumentParser(description="교재 등록 작업 도구")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("info"); p.add_argument("pdf")
    p = sub.add_parser("render"); p.add_argument("pdf"); p.add_argument("--pages", required=True)
    p.add_argument("--out", required=True); p.add_argument("--dpi", type=int, default=70)
    p = sub.add_parser("probe"); p.add_argument("pdf"); p.add_argument("--pages", required=True)
    p.add_argument("--ocr", action="store_true")
    p = sub.add_parser("extract"); p.add_argument("pdf"); p.add_argument("layout")
    p.add_argument("--out", required=True); p.add_argument("--pages"); p.add_argument("--no-sheets", action="store_true")
    p = sub.add_parser("ocrtext"); p.add_argument("pdf"); p.add_argument("--pages", required=True)
    p.add_argument("--lang", default="ko")
    p = sub.add_parser("units"); p.add_argument("problems"); p.add_argument("units")
    a = ap.parse_args()
    {"info": cmd_info, "render": cmd_render, "probe": cmd_probe,
     "extract": cmd_extract, "ocrtext": cmd_ocrtext, "units": cmd_units}[a.cmd](a)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
