# -*- coding: utf-8 -*-
"""검토를 마친 work/<slug> 들을 MYBOX 관리 기록에 '사용 가능'으로 등록 (오케스트레이터 전용).
    python work/register_ready.py <slug> [<slug> ...]
slug → 원본 경로는 SLUG_FILES(파일 이름 일부)로 work/_src/sources.json 에서 찾는다."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from core import books, registry as R  # noqa: E402

ROOT = r"N:\개인\내문서"
SLUG_FILES = {
    "마플내신연계_공수1_01다항식": "공수1내신연계문제-01",
    "마플내신연계_공수1_02방정식과부등식": "공수1내신연계문제-02",
    "마플내신연계_공수1_03경우의수": "공수1내신연계문제-03",
    "마플내신연계_공수1_04행렬": "공수1내신연계문제-04",
    "마플내신연계_공수2_01도형의방정식": "공수2내신연계문제－01",
    "마플내신연계_공수2_02집합과명제": "공수2내신연계문제－02",
    "마플내신연계_공수2_03함수와그래프": "공수2내신연계문제－03",
    "미래엔교과서_공통수학1": "미래엔(황선욱) 공통수학1 교과서 원본PDF",
    "미래엔교과서_공통수학2": "미래엔(황선욱) 공통수학2 교과서 원본",
    "비상문제북_공통수학1": "비상 공통수학1 수업 활용 문제북(학생용)",
    "비상문제북_공통수학2": "비상 공통수학2 수업 활용 문제북(학생용)",
    "비상편집본_공통수학1": "비상 공통수학1 편집본",
    "비상교과서_공통수학1": "비상 공통수학1(김원경) 교과서",
    "비상교과서_공통수학2": "비상 공통수학2(김원경) 교과서",
    "쎈_공통수학1": "/22개정 쎈 공통수학1.pdf",
    "쎈_공통수학2": "/22개정 쎈 공통수학2.pdf",
    "쎈B_공통수학1": "22개정 쎈B 공통수학1.pdf",
    "쎈B_공통수학2": "22개정 쎈B 공통수학2.pdf",
    "라이트쎈_공통수학1": "22개정 라이트쎈 공통수학1.pdf",
    "라이트쎈_공통수학2": "22개정 라이트쎈 공통수학2.pdf",
    "베이직쎈_공통수학1": "22개정 베이직쎈 공통수학1.pdf",
    "베이직쎈_공통수학2": "22개정 베이직쎈 공통수학2.pdf",
    "마플교과서_공통수학1": "22개정 공통수학1 마플교과서.pdf",
    "마플교과서_공통수학2": "22개정 공통수학2 마플교과서.pdf",
    "마플시너지_공통수학1": "22개정 공통수학1 마플시너지.pdf",
    "마플시너지_공통수학2": "22개정 공통수학2 마플시너지.pdf",
    "풍산자라이트_공통수학1": "22개정 공통수학1 풍산자 라이트.pdf",
    "풍산자라이트_공통수학2": "22개정 공통수학2 풍산자 라이트.pdf",
    "풍산자반복수학_공통수학1": "22개정 공통수학1 풍산자 반복수학.pdf",
    "풍산자반복수학_공통수학2": "22개정 공통수학2 풍산자 반복수학.pdf",
    "풍산자필수유형_공통수학1": "22개정 공통수학1 풍산자 필수유형.pdf",
    "풍산자필수유형_공통수학2": "22개정 공통수학2 풍산자 필수유형.pdf",
    "RPM_공통수학1": "22개정 RPM 공통수학1 학생용",
    "RPM_공통수학2": "22개정 RPM 공통수학2 학생용",
    "교과서유형별정리_공수1_01다항식": "[01_다항식]",
    "교과서유형별정리_공수1_02방정식과부등식1": "[02_방정식과 부등식(1)]",
    "교과서유형별정리_공수1_02방정식과부등식2": "[02_방정식과 부등식(2)]",
    "교과서유형별정리_공수1_03경우의수": "[03_경우의 수]",
    "교과서유형별정리_공수1_04행렬": "[04_행렬]",
}


def rel_for(slug, src):
    sp = os.path.join(HERE, slug, "SOURCE.txt")          # 에이전트가 적어 둔 원본 상대경로 (중3부터)
    if os.path.exists(sp):
        rel = open(sp, encoding="utf-8").read().strip().replace("\\", "/")
        if rel not in src:
            raise SystemExit(f"{slug}: SOURCE.txt 경로가 sources.json 에 없음: {rel}")
        return rel
    key = SLUG_FILES[slug]
    rels = [r for r in src if key in r]
    if len(rels) != 1:
        raise SystemExit(f"{slug}: 원본을 하나로 못 찾음 {rels}")
    return rels[0]


def same_content(rel, sha, src):
    out = []
    for other, local in src.items():
        if other != rel and os.path.exists(local) and os.path.getsize(local) == os.path.getsize(src[rel]):
            if R.sha256_file(local) == sha:
                out.append(other)
    return out


def main():
    src = json.load(open(os.path.join(HERE, "_src", "sources.json"), encoding="utf-8"))
    for slug in sys.argv[1:]:
        rel = rel_for(slug, src)
        wd = os.path.join(HERE, slug)
        n = len(json.load(open(os.path.join(wd, "problems.json"), encoding="utf-8"))["problems"])
        try:
            sha = books.register_from_work(ROOT, rel, wd, approve=True)
            print(f"✅ {slug}: {n}문제 → {rel}  ({sha[:10]})")
        except R.RegistryError as ex:
            print(f"❌ {slug}: {ex}")
            continue
        # 내용이 같은 다른 경로(이름만 다른 사본)도 같은 좌표로 등록
        for other in same_content(rel, sha, src):
            try:
                books.register_from_work(ROOT, other, wd, approve=True)
                print(f"   ↳ 같은 파일도 등록: {other}")
            except R.RegistryError as ex:
                print(f"   ↳ ❌ {other}: {ex}")


if __name__ == "__main__":
    main()
