# -*- coding: utf-8 -*-
"""RPM 미적분1 원본의 '회색/검은 큰 얼룩'을 없앤 사본 만들기 (검수·추출용, 원본은 건드리지 않음).

원인: 보이지 않는 풀이 글자층(렌더 모드 3)이 글자마다 Form XObject(/AGFA_TR 3)로 들어 있는데,
      그 Form 들이 경로를 만들고 칠하기 연산자 없이 'h' 로 끝남 → MuPDF(fitz)는 이 경로를 버리지 않고
      바로 뒤에 오는 칠하기(번호의 회색 '00' 등)와 합쳐서 그림 → 쪽마다 커다란 숫자 모양 얼룩.
      (Acrobat 등은 버리는 것으로 보임.) 각 Form 끝에 'n'(경로 버리기)을 붙이면 사라짐. 좌표는 그대로.

    python work/고2_RPM_미적분1/clean_pdf.py <원본.pdf> <사본.pdf>
"""
import sys

import fitz


def main():
    src, dst = sys.argv[1], sys.argv[2]
    d = fitz.open(src)
    n = 0
    for x in range(1, d.xref_length()):
        try:
            if d.xref_get_key(x, "Subtype")[1] != "/Form" or d.xref_get_key(x, "AGFA_TR")[1] != "3":
                continue
        except Exception:
            continue
        d.update_stream(x, d.xref_stream(x) + b"\nn\n")
        n += 1
    d.save(dst)
    print(f"Form {n}개 고침 → {dst}")


if __name__ == "__main__":
    main()
