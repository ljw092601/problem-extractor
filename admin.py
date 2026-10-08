# -*- coding: utf-8 -*-
"""
관리자용 명령줄 도구 (관리 화면을 만들기 전 임시/테스트용).

    python admin.py <자료폴더> scan [--dry-run]      폴더를 스캔해 신규/변경/삭제/이동을 기록
    python admin.py <자료폴더> status [--all]        상태별 개수 + 준비 중/사용 가능 목록
    python admin.py <자료폴더> suggest               파일명으로 본 제외 후보 (정답·해설·교사용 등)
    python admin.py <자료폴더> exclude <경로...>     제외 처리   (경로는 status 에 나온 상대경로)
    python admin.py <자료폴더> include <경로...>     제외 해제 → 준비 중
    python admin.py <자료폴더> register <경로> <problems_index.json> [--approve]
                                                   좌표 등록 → 검수 대기 (--approve 면 바로 사용 가능)
    python admin.py <자료폴더> register-work <경로> <work/slug 폴더> [--approve]
                                                   교재 작업 폴더(problems.json + units.json)로 등록
    python admin.py <자료폴더> approve <경로...>     검수 완료 → 사용 가능
    python admin.py <자료폴더> units <경로> <units.json>
                                                   단원 정보 넣기/바꾸기 (형식은 core/books.py 설명)
    python admin.py <자료폴더> history [-n 30]       최근 변경 내역

예:  python admin.py "N:\\개인\\내문서" scan --dry-run
"""
import argparse
import os
import sys
from collections import Counter

from core import books
from core import registry as R

EVENT_LABEL = {"added": "🆕 신규", "changed": "✏️ 변경", "removed": "🗑️ 삭제",
               "moved": "🔀 이동", "status": "🔁 상태", "registered": "📌 등록", "units": "📑 단원"}


def cmd_scan(root, args):
    res = R.scan(root)
    print(f"스캔 결과: {res.summary()}")
    for p in res.added:
        print("  🆕", p)
    for p in res.changed:
        print("  ✏️", p)
    for p in res.removed:
        print("  🗑️", p)
    for a, b in res.moved:
        print(f"  🔀 {a}  →  {b}")
    if args.dry_run:
        print("(--dry-run: 저장하지 않았습니다)")
        return
    R.apply(root, res)
    print("저장했습니다." if res.has_changes else "바뀐 것이 없습니다.")


def cmd_status(root, args):
    reg = R.load(root)
    files = reg["files"]
    if not files:
        print("기록이 없습니다. 먼저 scan 하세요.")
        return
    cnt = Counter(e.get("status") for e in files.values())
    print("  ".join(f"{R.STATUS_LABEL[s]} {cnt.get(s, 0)}" for s in R.STATUS_LABEL))
    shown = [R.APPROVED, R.REVIEW] + ([R.NEW, R.EXCLUDED] if args.all else [])
    for s in shown:
        items = [p for p, e in files.items() if e.get("status") == s]
        if items:
            print(f"\n[{R.STATUS_LABEL[s]}]")
            for p in items:
                print("  ", p)
    if not args.all:
        print("\n(준비 중·제외 목록까지 보려면 --all)")


def cmd_suggest(root, args):
    cands = R.exclude_candidates(R.load(root))
    print(f"제외 후보 {len(cands)}개 (파일명 기준):")
    for p in cands:
        print("  ", p)


def cmd_set(root, args, status):
    events = R.set_status(root, args.paths, status)
    print(f"{len(events)}개 변경 → {R.STATUS_LABEL[status]}")


def cmd_register(root, args):
    sha = books.register_from_index(root, args.path, args.index, approve=args.approve)
    print(f"등록 완료: {args.path}  ({'사용 가능' if args.approve else '검수 대기'}, 해시 {sha[:12]}…)")


def cmd_register_work(root, args):
    sha = books.register_from_work(root, args.path, args.work, approve=args.approve)
    print(f"등록 완료: {args.path}  ({'사용 가능' if args.approve else '검수 대기'}, 해시 {sha[:12]}…)")


def cmd_approve(root, args):
    reg = R.load(root)
    not_ready = [p for p in args.paths
                 if p in reg["files"] and not (reg["files"][p].get("sha256")
                                               and os.path.exists(R.coords_path(root, reg["files"][p]["sha256"])))]
    if not_ready:
        sys.exit("좌표가 없는 교재는 승인할 수 없어요: " + ", ".join(not_ready))
    cmd_set(root, args, R.APPROVED)


def cmd_units(root, args):
    import json
    with open(args.units, encoding="utf-8") as f:
        units = json.load(f)
    data = books.set_units(root, args.path, units)
    for g in books.unit_groups(data):
        print(f"  {g['title']}: 문제 {len(g['problems'])}개")


def cmd_history(root, args):
    for ev in R.read_history(root, args.n):
        what = EVENT_LABEL.get(ev["event"], ev["event"])
        extra = ""
        if ev["event"] == "moved":
            extra = f"  (← {ev['from']})"
        elif ev["event"] == "units":
            extra = f"  (단원 {ev.get('units')}개)"
        elif ev["event"] == "registered":
            extra = f"  (문제 {ev.get('problems')}개, {R.STATUS_LABEL.get(ev.get('to'), ev.get('to'))})"
        elif ev["event"] == "status":
            extra = f"  ({R.STATUS_LABEL.get(ev['from'], ev['from'])} → {R.STATUS_LABEL.get(ev['to'], ev['to'])})"
        print(f"{ev['t']}  {what}  {ev['path']}{extra}")


def main():
    ap = argparse.ArgumentParser(description="문제 추출기 관리자 도구")
    ap.add_argument("root", help="자료 폴더 (예: N:\\개인\\내문서)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scan"); p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("status"); p.add_argument("--all", action="store_true")
    sub.add_parser("suggest")
    p = sub.add_parser("exclude"); p.add_argument("paths", nargs="+")
    p = sub.add_parser("include"); p.add_argument("paths", nargs="+")
    p = sub.add_parser("register"); p.add_argument("path"); p.add_argument("index")
    p.add_argument("--approve", action="store_true")
    p = sub.add_parser("register-work"); p.add_argument("path"); p.add_argument("work")
    p.add_argument("--approve", action="store_true")
    p = sub.add_parser("approve"); p.add_argument("paths", nargs="+")
    p = sub.add_parser("units"); p.add_argument("path"); p.add_argument("units")
    p = sub.add_parser("history"); p.add_argument("-n", type=int, default=30)
    args = ap.parse_args()

    try:
        {"scan": cmd_scan, "status": cmd_status, "suggest": cmd_suggest, "history": cmd_history,
         "exclude": lambda r, a: cmd_set(r, a, R.EXCLUDED),
         "include": lambda r, a: cmd_set(r, a, R.NEW),
         "register": cmd_register, "register-work": cmd_register_work, "approve": cmd_approve, "units": cmd_units}[args.cmd](args.root, args)
    except R.RegistryError as ex:
        sys.exit(f"오류: {ex}")


if __name__ == "__main__":
    main()
