# -*- coding: utf-8 -*-
"""학년 폴더 PDF 목록(관리 상태·크기) 보기 + 로컬 사본 만들기 + 인벤토리 저장 (오케스트레이터 전용).
    python work/inventory.py 중2            # 목록만
    python work/inventory.py 중2 --copy     # work/_src/중2 로 사본 + sources.json·work/중2_inventory.json 갱신
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import fitz  # noqa: E402
from core import registry as R  # noqa: E402

ROOT = r"N:\개인\내문서"


def main():
    grade = sys.argv[1]
    copy = "--copy" in sys.argv
    reg = R.load(ROOT)
    files = reg["files"]
    rels = sorted(p for p in files if p.startswith(grade + "/"))
    src_path = os.path.join(HERE, "_src", "sources.json")
    sources = json.load(open(src_path, encoding="utf-8")) if os.path.exists(src_path) else {}
    inv = []
    for rel in rels:
        e = files[rel]
        full = R.file_path(ROOT, rel)                     # 한글 변환 PDF 는 관리 폴더에 있음
        size = os.path.getsize(full)
        print(f"{e.get('status', '?'):10s} {size / 1e6:7.1f}MB  {rel}")
        if not copy or e.get("status") == R.EXCLUDED:
            continue
        local = os.path.join(HERE, "_src", *rel.split("/"))
        if not (os.path.exists(local) and os.path.getsize(local) == size):
            os.makedirs(os.path.dirname(local), exist_ok=True)
            shutil.copy2(full, local)
        sources[rel] = local
        doc = fitz.open(local)
        p0 = doc[0]
        text = sum(len(doc[i].get_text()) for i in range(min(3, len(doc)))) > 200
        inv.append({"path": rel, "sha": R.sha256_file(local), "status": e.get("status"), "pages": len(doc),
                    "text": text, "rot": p0.rotation, "size": size, "w": round(p0.rect.width),
                    "h": round(p0.rect.height)})
    print(f"{len(rels)}개")
    if copy:
        json.dump(sources, open(src_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(inv, open(os.path.join(HERE, f"{grade}_inventory.json"), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("사본·인벤토리 저장")


if __name__ == "__main__":
    main()
