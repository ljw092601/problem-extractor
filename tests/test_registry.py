# -*- coding: utf-8 -*-
"""core/registry.py 시나리오 테스트:  python -m pytest tests -q"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import registry as R  # noqa: E402


def write(root, rel, data, mtime=None):
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "wb") as f:
        f.write(data)
    if mtime is not None:
        os.utime(p, (mtime, mtime))
    return p


def scan_apply(root):
    res = R.scan(root)
    R.apply(root, res)
    return res


@pytest.fixture
def root(tmp_path):
    r = str(tmp_path / "내문서")
    write(r, "고1/rpm/학생용.pdf", b"A" * 100, 1_000_000)
    write(r, "고1/rpm/정답.pdf", b"B" * 50, 1_000_000)
    write(r, "고2/교과서.pdf", b"C" * 70, 1_000_000)
    write(r, "고2/메모.hwp", b"x")                         # PDF 아님 → 무시
    return r


def approve(root, rel):
    """좌표화+승인을 흉내: 해시 기록, 좌표 파일 생성, 상태 approved."""
    reg = R.load(root)
    sha = R.sha256_file(os.path.join(root, *rel.split("/")))
    reg["files"][rel]["sha256"] = sha
    R.save(root, reg)
    R.atomic_write_json(R.coords_path(root, sha), {"problems": []})
    R.set_status(root, [rel], R.APPROVED)
    return sha


def test_first_scan_adds_only_pdfs(root):
    res = scan_apply(root)
    assert sorted(res.added) == ["고1/rpm/정답.pdf", "고1/rpm/학생용.pdf", "고2/교과서.pdf"]
    files = R.load(root)["files"]
    assert all(e["status"] == R.NEW and e["sha256"] is None for e in files.values())
    assert [e["event"] for e in R.read_history(root)] == ["added"] * 3


def test_rescan_without_changes_is_noop(root):
    scan_apply(root)
    res = R.scan(root)
    assert not res.has_changes and not res.touched


def test_changed_unhashed_file(root):
    scan_apply(root)
    write(root, "고2/교과서.pdf", b"C" * 71, 1_000_100)
    res = scan_apply(root)
    assert res.changed == ["고2/교과서.pdf"]


def test_approved_file_content_change_goes_back_to_new(root):
    scan_apply(root)
    old_sha = approve(root, "고1/rpm/학생용.pdf")
    write(root, "고1/rpm/학생용.pdf", b"Z" * 100, 1_000_200)   # 같은 크기, 다른 내용
    res = scan_apply(root)
    ent = R.load(root)["files"]["고1/rpm/학생용.pdf"]
    assert res.changed == ["고1/rpm/학생용.pdf"]
    assert ent["status"] == R.NEW and ent["sha256"] != old_sha


def test_approved_file_touched_keeps_status(root):
    scan_apply(root)
    approve(root, "고1/rpm/학생용.pdf")
    os.utime(os.path.join(root, "고1", "rpm", "학생용.pdf"), (2_000_000, 2_000_000))   # 시각만 바뀜
    res = scan_apply(root)
    assert not res.has_changes and res.touched == ["고1/rpm/학생용.pdf"]
    assert R.load(root)["files"]["고1/rpm/학생용.pdf"]["status"] == R.APPROVED


def test_move_keeps_approval(root):
    scan_apply(root)
    sha = approve(root, "고1/rpm/학생용.pdf")
    os.makedirs(os.path.join(root, "고1", "새폴더"))
    os.replace(os.path.join(root, "고1", "rpm", "학생용.pdf"), os.path.join(root, "고1", "새폴더", "학생용(개정).pdf"))
    res = scan_apply(root)
    assert res.moved == [("고1/rpm/학생용.pdf", "고1/새폴더/학생용(개정).pdf")]
    assert not res.added and not res.removed
    ent = R.load(root)["files"]["고1/새폴더/학생용(개정).pdf"]
    assert ent["status"] == R.APPROVED and ent["sha256"] == sha


def test_removed(root):
    scan_apply(root)
    os.remove(os.path.join(root, "고2", "교과서.pdf"))
    res = scan_apply(root)
    assert res.removed == ["고2/교과서.pdf"]
    assert "고2/교과서.pdf" not in R.load(root)["files"]


def test_exclude_and_suggest(root):
    scan_apply(root)
    reg = R.load(root)
    assert R.exclude_candidates(reg) == ["고1/rpm/정답.pdf"]
    R.set_status(root, ["고1/rpm/정답.pdf"], R.EXCLUDED)
    reg = R.load(root)
    assert R.exclude_candidates(reg) == []
    st = reg["files"]["고1/rpm/정답.pdf"]
    assert R.book_state(root, "고1/rpm/정답.pdf", st["size"], st["mtime"], reg) == R.HIDDEN


def test_excluded_stays_excluded_after_change(root):
    scan_apply(root)
    R.set_status(root, ["고1/rpm/정답.pdf"], R.EXCLUDED)
    write(root, "고1/rpm/정답.pdf", b"B" * 51, 1_000_300)
    scan_apply(root)
    assert R.load(root)["files"]["고1/rpm/정답.pdf"]["status"] == R.EXCLUDED


def test_teacher_book_state_and_verify(root):
    scan_apply(root)
    rel = "고1/rpm/학생용.pdf"
    reg = R.load(root)
    e = reg["files"][rel]
    assert R.book_state(root, rel, e["size"], e["mtime"], reg) == R.PREPARING
    approve(root, rel)
    reg = R.load(root)
    e = reg["files"][rel]
    assert R.book_state(root, rel, e["size"], e["mtime"], reg) == R.READY
    assert R.verify(root, rel, reg).endswith(".json")
    # 관리자가 스캔하기 전에 파일이 바뀐 경우: 목록은 크기/시각으로 '준비 중', 열 때 해시로 막힘
    write(root, rel, b"Q" * 100, 1_000_000)             # 크기·시각까지 같게 바꿔도
    assert R.book_state(root, rel, e["size"], e["mtime"], reg) == R.READY
    with pytest.raises(R.RegistryError):
        R.verify(root, rel, reg)                        # 해시에서 걸림
    # 새로 생긴(아직 스캔 안 된) 파일은 준비 중
    assert R.book_state(root, "고3/새책.pdf", 1, 1, reg) == R.PREPARING


def test_registry_is_valid_json_and_history_appends(root):
    scan_apply(root)
    R.set_status(root, ["고2/교과서.pdf"], R.EXCLUDED)
    with open(R.admin_path(root, R.REGISTRY), encoding="utf-8") as f:
        json.load(f)
    events = [e["event"] for e in R.read_history(root)]
    assert events == ["added"] * 3 + ["status"]
    leftovers = [n for n in os.listdir(R.admin_path(root)) if n.startswith("tmp-")]
    assert leftovers == []


def test_missing_root_gives_friendly_error(tmp_path):
    with pytest.raises(R.RegistryError, match="MYBOX"):
        R.scan(str(tmp_path / "없는폴더"))


def test_selector_bad_tokens_do_not_crash():
    import selector
    entries = [{"num": n, "page": 1} for n in range(1, 6)]
    chosen, errors = selector.resolve(["a:5", "4-2", "1:2-3", "x"], entries)
    assert [e["num"] for e in chosen] == [2, 3]
    assert len(errors) == 3


def test_units_split_mid_page_and_fallback_groups():
    from core import books
    probs = [{"id": f"{pg}-{n}", "num": n, "page": pg, "pdf_page": pg - 1, "column": col, "bbox": [0, y, 1, y + 10]}
             for n, (pg, col, y) in enumerate([(1, "L", 100), (1, "R", 100), (2, "L", 100), (2, "R", 50),
                                               (2, "R", 400), (13, "L", 10)], 1)]
    units = [{"id": "a", "title": "A", "start": {"page": 1, "column": "L", "y": 0}},
             {"id": "b", "title": "B", "start": {"page": 2, "column": "R", "y": 300}}]   # 2쪽 오른쪽 단 중간부터 B
    books.assign_units(probs, units)
    assert [p["unit"] for p in probs] == ["a", "a", "a", "a", "b", "b"]
    groups = books.unit_groups({"problems": probs, "units": units})
    assert [(g["title"], len(g["problems"])) for g in groups] == [("A", 4), ("B", 2)]
    books.assign_units(probs, [])
    groups = books.unit_groups({"problems": probs, "units": []})
    assert [(g["title"], len(g["problems"])) for g in groups] == [("1~2쪽", 5), ("13쪽", 1)]


def test_load_missing_root_raises_instead_of_empty(tmp_path):
    with pytest.raises(R.RegistryError, match="MYBOX"):
        R.load(str(tmp_path / "끊긴드라이브"))


def test_merge_continued_and_stitched_crop(tmp_path):
    import fitz
    import selector
    from core import books
    probs = [{"num": 5, "page": 1, "pdf_page": 0, "column": "L", "bbox": [0, 0, 100, 50]},
             {"num": 6, "page": 1, "pdf_page": 0, "column": "L", "bbox": [0, 60, 100, 120]},
             {"num": 6, "page": 1, "pdf_page": 0, "column": "R", "bbox": [110, 0, 200, 80], "continued": True},
             {"num": 7, "page": 2, "pdf_page": 1, "column": "L", "bbox": [0, 0, 100, 40]}]
    m = books.merge_continued(probs)
    assert [p["num"] for p in m] == [5, 6, 7]
    assert m[1]["parts"] == [{"pdf_page": 0, "page": 1, "bbox": [110, 0, 200, 80]}]
    doc = fitz.open(); doc.new_page(width=200, height=200); doc.new_page(width=200, height=200)
    it = selector.crop_item(doc, m[1])
    import template as T
    assert abs(it["pix"].height - (60 + 80) * T.RENDER_DPI / 72) < 3      # 두 조각 높이의 합
    assert abs(it["pix"].width - 100 * T.RENDER_DPI / 72) < 3             # 넓은 쪽 폭


def test_auto_cols_uses_width_relative_to_page():
    import selector
    assert selector.auto_cols([{"rel_w": 0.88}, {"rel_w": 0.9}, {"rel_w": 0.4}]) == 1
    assert selector.auto_cols([{"rel_w": 0.41}, {"rel_w": 0.45}, {"rel_w": 0.9}]) == 2
    assert selector.auto_cols([]) == 2


def test_group_spilling_into_next_column_is_merged():
    from core import books
    probs = [{"num": 140, "num_end": 150, "page": 27, "pdf_page": 26, "column": "L", "bbox": [0, 500, 100, 770]},
             {"num": 145, "page": 27, "pdf_page": 26, "column": "R", "bbox": [110, 58, 200, 78]},
             {"num": 146, "num_end": 150, "page": 27, "pdf_page": 26, "column": "R", "bbox": [110, 80, 200, 300]},
             {"num": 151, "num_end": 158, "page": 27, "pdf_page": 26, "column": "R", "bbox": [110, 400, 200, 760]},
             {"num": 152, "page": 28, "pdf_page": 27, "column": "L", "bbox": [0, 60, 100, 90]}]
    m = books.merge_continued(probs)
    assert [(p["num"], len(p.get("parts", []))) for p in m] == [(140, 2), (151, 1)]
