# -*- coding: utf-8 -*-
"""
관리 폴더(_문제추출_관리)와 변경 내역 추적 — git 처럼 '지난 기록 vs 지금 폴더'를 비교한다.

자료 폴더(예: N:\\개인\\내문서) 구조:
    <root>\\
      ├─ 고1\\ 고2\\ ...                    (기존 자료 — 읽기만 함)
      └─ _문제추출_관리\\                   (이 프로그램 전용)
           ├─ registry.json                 파일별 기록: 크기, 수정 시각, 해시, 상태
           ├─ history.log                   변경 내역 (한 줄에 JSON 하나, 덧붙이기만 함)
           └─ coords\\<sha256>.json          문제 좌표 (내용 해시 기준 → 이름을 바꾸거나 옮겨도 유지)

상태(status):
    new       준비 중 — 아직 좌표화 안 됨 (신규, 또는 내용이 바뀜)
    review    준비 중 — 좌표는 있고 관리자 검수 대기
    approved  사용 가능 — 검수·승인 완료
    excluded  제외 — 정답지·교사용 부록 등. 선생님 화면에 안 보임

성능 원칙 (MYBOX 는 파일을 열면 내려받으므로):
    - 목록/스캔은 크기 + 수정 시각만 비교한다.
    - 해시는 꼭 필요할 때만: 해시가 기록된 파일의 크기·시각이 바뀌었을 때, 이동 여부를 확인할 때,
      선생님이 교재를 열 때(verify), 관리자가 좌표화할 때.

쓰기는 관리자 도구만 한다. 선생님 쪽은 load / book_state / verify 만 쓴다(읽기 전용).
"""
import hashlib
import json
import os
import re
import socket
import tempfile
import time
from dataclasses import dataclass, field

ADMIN_DIR = "_문제추출_관리"
REGISTRY = "registry.json"
HISTORY = "history.log"
COORDS_DIR = "coords"

NEW, REVIEW, APPROVED, EXCLUDED = "new", "review", "approved", "excluded"
STATUS_LABEL = {NEW: "준비 중(미좌표화)", REVIEW: "준비 중(검수 대기)",
                APPROVED: "사용 가능", EXCLUDED: "제외"}

# 파일명에 이 단어가 있으면 '제외 후보'로 추천 (자동 제외는 하지 않음)
EXCLUDE_HINT = re.compile(r"정답|해설|답지|교사용|부록")


class RegistryError(Exception):
    """사용자에게 그대로 보여줄 수 있는 문구를 담는 오류."""


# ---------------------------------------------------------------- 파일 유틸

def admin_path(root, *parts):
    return os.path.join(root, ADMIN_DIR, *parts)


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def atomic_write_json(path, data):
    """임시 파일에 다 쓴 뒤 이름을 바꾼다 → 동기화 중에 반쯤 쓴 파일이 퍼지지 않음."""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    # MYBOX 는 '.' 으로 시작하는 파일 생성을 막는다(mkstemp 가 그 오류에 무한 재시도하며 멈춤) → 점 없는 이름
    fd, tmp = tempfile.mkstemp(prefix="tmp-", suffix=".json", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        for attempt in range(10):                        # MYBOX 가 방금 쓴 파일을 올리는 중이면 잠깐 잠김
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                if attempt == 9:
                    raise
                time.sleep(1 + attempt)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


# 한글(.hwp) 파일을 PDF 로 바꾼 것 (hwp_convert.py). 교재 폴더를 어지럽히지 않게 관리 폴더에 두되,
# 목록·등록에서는 원래 한글 파일이 있던 자리의 경로('고3/…/이름.pdf')로 다룬다.
CONVERTED_DIR = (ADMIN_DIR, "한글변환", "PDF")


def file_path(root, rel):
    """상대경로 → 실제 파일 경로. 교재 폴더에 없으면 한글 변환 PDF 폴더에서 찾는다."""
    p = os.path.join(root, *rel.split("/"))
    if os.path.exists(p):
        return p
    q = os.path.join(root, *CONVERTED_DIR, *rel.split("/"))
    return q if os.path.exists(q) else p


def _walk(base, skip_admin):
    found = {}
    stack = [""]
    while stack:
        rel_dir = stack.pop()
        try:
            it = os.scandir(os.path.join(base, rel_dir))
        except OSError:
            continue                                   # 권한 없음·동기화 중 → 이번 스캔에서만 건너뜀
        with it:
            for e in it:
                if e.name.startswith((".", "~$", "tmp-")) or (skip_admin and e.name == ADMIN_DIR):
                    continue
                rel = f"{rel_dir}/{e.name}" if rel_dir else e.name
                try:
                    if e.is_dir(follow_symlinks=False):
                        stack.append(rel)
                    elif e.name.lower().endswith(".pdf"):
                        st = e.stat()
                        found[rel] = (st.st_size, int(st.st_mtime))
                except OSError:
                    continue
    return found


def walk_pdfs(root):
    """root 아래 모든 PDF → {상대경로('/' 구분): (크기, 수정 시각 초)}. 관리 폴더·숨김 폴더는 건너뜀.
    한글 변환 PDF 도 원래 자리 경로로 포함한다 (같은 경로의 진짜 PDF 가 있으면 그쪽이 우선)."""
    if not os.path.isdir(root):
        raise RegistryError(f"교재 폴더에 연결할 수 없어요: {root}\nMYBOX가 실행·로그인되어 있는지 확인해 주세요.")
    found = _walk(root, skip_admin=True)
    conv = os.path.join(root, *CONVERTED_DIR)
    if os.path.isdir(conv):
        for rel, v in _walk(conv, skip_admin=False).items():
            found.setdefault(rel, v)
    return found


# ---------------------------------------------------------------- 기록

def empty_registry():
    return {"version": 1, "updated_at": None, "files": {}}


def load(root):
    """registry.json 읽기. 없으면 빈 기록. 깨졌으면(동기화 중 등) RegistryError.
    자료 폴더 자체가 없으면(MYBOX 끊김) 빈 기록이 아니라 RegistryError — 빈 기록을 저장하는 사고 방지."""
    if not os.path.isdir(root):
        raise RegistryError(f"교재 폴더에 연결할 수 없어요: {root}\nMYBOX가 실행·로그인되어 있는지 확인해 주세요.")
    p = admin_path(root, REGISTRY)
    if not os.path.exists(p):
        return empty_registry()
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as ex:
        raise RegistryError("관리 기록(registry.json)을 읽지 못했어요. 동기화 중일 수 있으니 잠시 후 다시 시도해 주세요.") from ex
    data.setdefault("files", {})
    return data


def save(root, reg):
    reg["updated_at"] = now_iso()
    atomic_write_json(admin_path(root, REGISTRY), reg)


def append_history(root, events):
    if not events:
        return
    os.makedirs(admin_path(root), exist_ok=True)
    by = os.environ.get("COMPUTERNAME") or socket.gethostname()
    with open(admin_path(root, HISTORY), "a", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps({"t": now_iso(), "by": by, **ev}, ensure_ascii=False) + "\n")


def read_history(root, limit=None):
    p = admin_path(root, HISTORY)
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue                           # 깨진 줄은 무시
    return out[-limit:] if limit else out


def coords_path(root, sha):
    return admin_path(root, COORDS_DIR, f"{sha}.json")


# ---------------------------------------------------------------- 스캔 (관리자)

@dataclass
class ScanResult:
    """지난 기록과 지금 폴더의 차이. apply() 전까지는 아무것도 쓰지 않는다."""
    added: list = field(default_factory=list)      # [경로]
    changed: list = field(default_factory=list)    # [경로]  내용이 바뀜
    removed: list = field(default_factory=list)    # [경로]
    moved: list = field(default_factory=list)      # [(이전 경로, 새 경로)]
    touched: list = field(default_factory=list)    # [경로]  시각만 바뀌고 내용은 같음(기록만 갱신)
    new_registry: dict = None
    events: list = field(default_factory=list)

    @property
    def has_changes(self):
        return bool(self.added or self.changed or self.removed or self.moved)

    def summary(self):
        return (f"신규 {len(self.added)} · 변경 {len(self.changed)} · "
                f"삭제 {len(self.removed)} · 이동 {len(self.moved)}")


def scan(root, reg=None, hasher=sha256_file):
    """폴더를 스캔해 기록과 비교한다. 결과의 new_registry/events 를 apply() 로 저장."""
    reg = reg if reg is not None else load(root)
    old = reg["files"]
    disk = walk_pdfs(root)
    new = {}
    res = ScanResult()
    t = now_iso()

    def full(rel):
        return file_path(root, rel)

    added = sorted(set(disk) - set(old))
    removed = sorted(set(old) - set(disk))

    # 1) 이동/이름 변경: 사라진 파일 중 해시가 기록된 것 ↔ 새로 생긴 같은 크기 파일을 해시로 대조
    added_left = list(added)
    for rp in removed:
        ent = old[rp]
        if not ent.get("sha256"):
            continue
        for ap in [a for a in added_left if disk[a][0] == ent["size"]]:
            try:
                if hasher(full(ap)) == ent["sha256"]:
                    new[ap] = {**ent, "size": disk[ap][0], "mtime": disk[ap][1], "updated_at": t}
                    res.moved.append((rp, ap))
                    res.events.append({"event": "moved", "from": rp, "path": ap, "sha256": ent["sha256"]})
                    added_left.remove(ap)
                    break
            except OSError:
                continue
    moved_from = {m[0] for m in res.moved}

    # 2) 그대로 있는 파일: 크기·시각이 같으면 그대로, 다르면 확인
    for rp in sorted(set(disk) & set(old)):
        ent = dict(old[rp])
        size, mtime = disk[rp]
        if (size, mtime) == (ent.get("size"), ent.get("mtime")):
            new[rp] = ent
            continue
        ent.update(size=size, mtime=mtime, updated_at=t)
        if ent.get("sha256"):
            try:
                sha = hasher(full(rp))
            except OSError:
                new[rp] = old[rp]                      # 못 읽음(동기화 중) → 이번엔 기록 유지
                continue
            if sha == ent["sha256"]:
                res.touched.append(rp)
                new[rp] = ent
                continue
            res.events.append({"event": "changed", "path": rp, "old_sha256": ent["sha256"], "sha256": sha})
            ent["sha256"] = sha
        else:
            res.events.append({"event": "changed", "path": rp})
        if ent.get("status") != EXCLUDED:
            ent["status"] = NEW                        # 내용이 바뀜 → 이전 좌표 사용 중지
        res.changed.append(rp)
        new[rp] = ent

    # 3) 신규
    for ap in added_left:
        new[ap] = {"size": disk[ap][0], "mtime": disk[ap][1], "sha256": None,
                   "status": NEW, "first_seen": t, "updated_at": t}
        res.added.append(ap)
        res.events.append({"event": "added", "path": ap})

    # 4) 삭제 (이동으로 판명된 것 제외)
    for rp in removed:
        if rp in moved_from:
            continue
        res.removed.append(rp)
        res.events.append({"event": "removed", "path": rp, "sha256": old[rp].get("sha256"),
                           "status": old[rp].get("status")})

    res.new_registry = {**reg, "files": dict(sorted(new.items()))}
    return res


def apply(root, result):
    """scan() 결과를 저장한다 (registry 원자적 저장 + history 덧붙이기)."""
    if not result.has_changes and not result.touched:
        return
    save(root, result.new_registry)
    append_history(root, result.events)


# ---------------------------------------------------------------- 상태 변경 (관리자)

def set_status(root, paths, status, reg=None, note=None):
    """여러 파일의 상태를 바꾸고 기록한다. 없는 경로는 RegistryError."""
    if status not in STATUS_LABEL:
        raise RegistryError(f"알 수 없는 상태: {status}")
    reg = reg if reg is not None else load(root)
    files = reg["files"]
    missing = [p for p in paths if p not in files]
    if missing:
        raise RegistryError("기록에 없는 파일이에요 (먼저 스캔하세요): " + ", ".join(missing))
    events = []
    for p in paths:
        before = files[p].get("status")
        if before == status:
            continue
        files[p] = {**files[p], "status": status, "updated_at": now_iso()}
        ev = {"event": "status", "path": p, "from": before, "to": status}
        if note:
            ev["note"] = note
        events.append(ev)
    if events:
        save(root, reg)
        append_history(root, events)
    return events


def exclude_candidates(reg):
    """파일명으로 본 제외 후보 (아직 제외되지 않은 것만)."""
    return [p for p, e in reg["files"].items()
            if e.get("status") != EXCLUDED and EXCLUDE_HINT.search(p.rsplit("/", 1)[-1])]


# ---------------------------------------------------------------- 선생님 쪽 (읽기 전용)

READY, PREPARING, HIDDEN = "ready", "preparing", "hidden"


def book_state(root, rel, size, mtime, reg):
    """목록 표시용 상태 (해시 없이 빠르게). ready / preparing / hidden"""
    ent = reg["files"].get(rel)
    if ent is None:
        return PREPARING                                # 관리자가 아직 스캔 안 한 새 파일
    if ent.get("status") == EXCLUDED:
        return HIDDEN
    if (ent.get("status") == APPROVED and ent.get("sha256")
            and (size, mtime) == (ent.get("size"), ent.get("mtime"))
            and os.path.exists(coords_path(root, ent["sha256"]))):
        return READY
    return PREPARING


def verify(root, rel, reg):
    """교재를 열 때: 실제 해시가 승인된 해시와 같은지 확인. 같으면 좌표 파일 경로, 다르면 RegistryError."""
    ent = reg["files"].get(rel)
    if not ent or ent.get("status") != APPROVED or not ent.get("sha256"):
        raise RegistryError("아직 준비 중인 교재예요.")
    try:
        sha = sha256_file(file_path(root, rel))
    except OSError as ex:
        raise RegistryError("교재 파일을 열 수 없어요. 동기화 중인지 확인해 주세요.") from ex
    if sha != ent["sha256"]:
        raise RegistryError("교재 파일이 등록 이후 바뀌었어요. 관리자에게 다시 등록을 요청해 주세요.")
    cp = coords_path(root, sha)
    if not os.path.exists(cp):
        raise RegistryError("문제 위치 정보가 없어요. 관리자에게 문의해 주세요.")
    return cp
