# -*- coding: utf-8 -*-
"""
교재 등록(좌표 저장)과 좌표 읽기.

좌표 파일: <root>\\_문제추출_관리\\coords\\<sha256>.json
    {
      "version": 1,
      "sha256": "...", "page_count": 4, "source_name": "원래 파일 이름.pdf",
      "created_at": "...", "layout": {...좌표를 만들 때 쓴 설정(있으면)},
      "problems": [ {"id": "1-1", "num": 1, "page": 1, "pdf_page": 0, "column": "L",
                     "bbox": [x0, y0, x1, y1]}, ... ]
    }
  - page     : 사용자에게 보이는 쪽 (1부터)
  - pdf_page : PDF 안의 순번 (0부터)
  - id       : 교재 안에서 유일 ('쪽-번호', 같은 쪽에 같은 번호가 또 있으면 '-2' 붙임)
  - unit     : 속한 단원 id (단원 정보가 있을 때)

단원 (선택): "units": [ {"id": "u1", "title": "01 경우의 수", "group": "Ⅰ. 경우의 수",
                        "start": {"page": 1, "column": "L", "y": 0}}, ... ]
  - start 는 단원 제목 위치. 문제를 읽는 순서(쪽 → 왼쪽 단 → 오른쪽 단 → 위에서 아래)로 놓고
    '시작점이 문제보다 앞선 마지막 단원'에 넣는다 → 단원이 쪽 중간에서 바뀌어도 된다.
  - group 은 대단원 이름(선택). 선생님 화면에서 단원을 묶어 보여 준다.
  - 단원 정보가 없으면 선생님 화면은 10쪽씩 묶어 보여 준다.
"""
import json
import os

import fitz

from . import registry as R


def _with_ids(problems):
    seen, out = {}, []
    for p in problems:
        base = f"{p['page']}-{p['num']}"
        seen[base] = seen.get(base, 0) + 1
        pid = base if seen[base] == 1 else f"{base}-{seen[base]}"
        out.append({"id": pid, **{k: p[k] for k in ("num", "num_end", "page", "pdf_page", "column", "bbox", "parts")
                                  if k in p}})
    return out


def merge_continued(problems):
    """'continued: true' 인 조각(앞 문제가 다음 단·쪽으로 이어진 부분)을 바로 앞 문제의 parts 로 붙인다.
    parts = [{"pdf_page", "page", "bbox"}] — 자를 때 본 영역 아래에 차례로 이어 붙인다."""
    out = []
    for p in problems:
        prev = out[-1] if out else None
        # 단·쪽을 넘어간 묶음: 앞 묶음 [a~b] 바로 뒤에 오는 문제의 번호가 그 범위 안이면 이어진 부분
        other_col = prev is not None and (p["page"], p.get("column")) != (prev["page"], prev.get("column"))
        spill = other_col and (
            (prev.get("num_end") and prev["num"] < p["num"] <= prev["num_end"]
             and p.get("num_end", p["num"]) <= prev["num_end"])
            # 같은 번호가 다음 단·쪽에 또 나오면(문제 뒷부분만 넘어간 조각) 이어진 부분
            or (p["num"] == prev["num"] and not p.get("num_end") and not prev.get("num_end")))
        if (p.get("continued") or spill) and out:
            merged = {**out[-1], "parts": out[-1].get("parts", []) +
                      [{"pdf_page": p["pdf_page"], "page": p["page"], "bbox": p["bbox"]}]}
            end = max(merged.get("num_end", merged["num"]), p.get("num_end", p["num"]))
            if end > merged["num"]:
                merged["num_end"] = end                  # 이어진 소문제 번호까지 묶음 범위를 넓힘
            out[-1] = merged
        else:
            out.append({k: v for k, v in p.items() if k != "continued"})
    return out


def _reading_key(page, column, y):
    return (page, 1 if column == "R" else 0, y)


def assign_units(problems, units):
    """문제마다 unit 을 채운다(읽는 순서 기준). 첫 단원보다 앞선 문제는 첫 단원에 넣는다."""
    if not units:
        for p in problems:
            p.pop("unit", None)
        return problems
    starts = sorted(((_reading_key(u["start"]["page"], u["start"].get("column", "L"), u["start"].get("y", 0)), u["id"])
                     for u in units))
    for p in problems:
        key = _reading_key(p["page"], p.get("column", "L"), p["bbox"][1])
        uid = starts[0][1]
        for s, sid in starts:
            if s <= key:
                uid = sid
        p["unit"] = uid
    return problems


def _check_units(units):
    ids = [u.get("id") for u in units]
    if len(set(ids)) != len(ids) or not all(ids):
        raise R.RegistryError("단원 id 가 비었거나 겹쳐요.")
    for u in units:
        if not u.get("title") or "page" not in u.get("start", {}):
            raise R.RegistryError(f"단원 정보가 모자라요 (title, start.page 필요): {u}")


def register(root, rel, problems, layout=None, approve=False, reg=None, units=None):
    """rel(자료 폴더 기준 상대경로) 교재의 좌표를 저장하고 상태를 검수 대기(또는 승인)로 바꾼다."""
    reg = reg if reg is not None else R.load(root)
    if rel not in reg["files"]:
        raise R.RegistryError(f"기록에 없는 파일이에요 (먼저 스캔하세요): {rel}")
    if not problems:
        raise R.RegistryError("문제 좌표가 비어 있어요.")
    path = R.file_path(root, rel)
    sha = R.sha256_file(path)
    with fitz.open(path) as d:
        page_count = d.page_count
    bad = [p for p in problems if not 0 <= p["pdf_page"] < page_count]
    if bad:
        raise R.RegistryError(f"PDF에 없는 쪽을 가리키는 좌표가 {len(bad)}개 있어요.")
    units = units or []
    _check_units(units)

    R.atomic_write_json(R.coords_path(root, sha), {
        "version": 1, "sha256": sha, "page_count": page_count,
        "source_name": os.path.basename(path), "created_at": R.now_iso(),
        "layout": layout or {}, "units": units,
        "problems": assign_units(_with_ids(merge_continued(problems)), units),
    })
    st = os.stat(path)
    ent = reg["files"][rel]
    status = R.APPROVED if approve else R.REVIEW
    reg["files"][rel] = {**ent, "sha256": sha, "size": st.st_size, "mtime": int(st.st_mtime),
                         "status": status, "updated_at": R.now_iso()}
    R.save(root, reg)
    R.append_history(root, [{"event": "registered", "path": rel, "sha256": sha,
                             "problems": len(problems), "to": status}])
    return sha


def register_from_index(root, rel, index_path, approve=False):
    """기존 problems_index.json(index_problems.py 결과)으로 등록."""
    with open(index_path, encoding="utf-8") as f:
        data = json.load(f)
    return register(root, rel, data["problems"], layout={"from": os.path.basename(index_path)},
                    approve=approve)


def register_from_work(root, rel, work_dir, approve=False):
    """교재 작업 폴더(work/<slug>: problems.json, units.json, layout.json)로 등록."""
    def read(name, default=None):
        p = os.path.join(work_dir, name)
        if not os.path.exists(p):
            if default is not None:
                return default
            raise R.RegistryError(f"작업 폴더에 {name} 이 없어요: {work_dir}")
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    problems = read("problems.json")["problems"]
    units = read("units.json", [])
    layout = read("layout.json", {})
    layout = {**layout, "work_dir": os.path.basename(os.path.normpath(work_dir))}
    return register(root, rel, problems, layout=layout, approve=approve, units=units)


def set_units(root, rel, units):
    """이미 등록된 교재의 단원 정보만 바꾼다 (PDF·좌표는 그대로)."""
    _check_units(units)
    reg = R.load(root)
    ent = reg["files"].get(rel)
    if not ent or not ent.get("sha256") or not os.path.exists(R.coords_path(root, ent["sha256"])):
        raise R.RegistryError(f"좌표가 등록되지 않은 교재예요: {rel}")
    cp = R.coords_path(root, ent["sha256"])
    data = load_coords(cp)
    data["units"] = units
    assign_units(data["problems"], units)
    R.atomic_write_json(cp, data)
    R.append_history(root, [{"event": "units", "path": rel, "units": len(units)}])
    return data


def load_coords(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["problems"] = data.get("problems", [])
    data["units"] = data.get("units", [])
    if (data.get("layout") or {}).get("render_clean"):      # 그리기 전 쪽 정리가 필요한 교재 (core/pdfpage.py)
        for p in data["problems"]:
            p["clean"] = True
    return data


def unit_groups(coords, pages_per_group=10):
    """선생님 화면용 묶음: [{"id", "title", "group", "problems": [...]}] (문제 없는 단원은 뺌).
    단원 정보가 없으면 10쪽씩 묶는다."""
    probs = coords["problems"]
    units = coords.get("units") or []
    if units and all("unit" in p for p in probs):
        out = []
        for u in units:
            ps = [p for p in probs if p["unit"] == u["id"]]
            if ps:
                out.append({"id": u["id"], "title": u["title"], "group": u.get("group"), "problems": ps})
        return out
    out = {}
    for p in probs:
        g = (p["page"] - 1) // pages_per_group
        out.setdefault(g, []).append(p)
    return [{"id": f"pages-{g}", "group": None,
             "title": f"{ps[0]['page']}~{ps[-1]['page']}쪽" if ps[0]["page"] != ps[-1]["page"] else f"{ps[0]['page']}쪽",
             "problems": ps} for g, ps in sorted(out.items())]
