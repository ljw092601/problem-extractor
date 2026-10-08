# -*- coding: utf-8 -*-
"""
쪽 그리기 전 준비.

일부 교재 PDF 는 MuPDF(fitz)로 그리면 문제 위에 큰 얼룩이 생기거나(RPM 미적분1: 보이지 않는 풀이
글자층이 칠하지 않은 경로를 남김) 글자가 통째로 빠진다(수력충전 대수: 그리기 명령이 꼬임).
page.clean_contents() 로 쪽 내용을 정리하면 정상으로 그려지고 좌표는 그대로다.
원본 파일은 건드리지 않고 **열린 문서(메모리)에서만** 정리한다.

좌표 파일의 layout 에 "render_clean": true 인 교재만 적용 (books.load_coords 가 문제마다 "clean" 표시).
"""


def ready_page(doc, pno, clean=False):
    """doc[pno] 를 돌려준다. clean 이면 그리기 전에 한 번만 쪽 내용을 정리한다."""
    page = doc[pno]
    if clean:
        done = getattr(doc, "_cleaned_pages", None)
        if done is None:
            done = set()
            doc._cleaned_pages = done
        if pno not in done:
            page.clean_contents()
            done.add(pno)
            page = doc[pno]
    return page
