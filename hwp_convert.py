# -*- coding: utf-8 -*-
"""
한글 변환기 (관리자용, 한글이 설치된 PC 에서 실행).

교재 폴더(MYBOX 내문서)의 한글 파일(.hwp/.hwpx)을 한글 프로그램으로 열어
  - PDF  → _문제추출_관리/한글변환/PDF/<원본과 같은 경로>/원본이름.pdf
           (교재 폴더에 같은 이름 PDF 가 이미 있으면 '원본이름 (한글변환).pdf')
           선생님 앱은 이 PDF 를 원래 한글 파일이 있던 폴더에 있는 것처럼 보여 준다 (core/registry.file_path)
  - HWPX → _문제추출_관리/한글변환/hwpx/<같은 경로>.hwpx  (나중에 '원본 그대로 복사' 기능용)
로 저장한다. 원본 한글 파일은 건드리지 않는다.
이미 변환한 파일(원본 크기·수정 시각이 같음)은 건너뛰므로 여러 번 실행해도 된다.

    한글변환기.exe                    # N:\개인\내문서 전체
    한글변환기.exe --root D:\교재      # 다른 교재 폴더
    한글변환기.exe --only 고3          # 일부 폴더만
    한글변환기.exe --dry-run           # 변환하지 않고 대상만 보기

한글 자동화는 파일을 열 때 '접근 허용' 확인 창을 띄울 수 있다 → [모두 허용]을 누르면 이후 자동 진행.
"""
import argparse
import datetime
import json
import os
import shutil
import sys
import tempfile
import time
import traceback

DEFAULT_ROOT = r"N:\개인\내문서"
ADMIN_DIR = "_문제추출_관리"
OUT_DIR = "한글변환"


def conv_pdf_path(root, pdf_rel):
    """원래 자리 기준 경로('고3/…/이름.pdf') → 관리 폴더 안 실제 저장 위치"""
    return os.path.join(root, ADMIN_DIR, OUT_DIR, "PDF", *pdf_rel.split("/"))


def log_line(fp, msg):
    line = f"{datetime.datetime.now():%H:%M:%S}  {msg}"
    try:
        print(line, flush=True)
    except Exception:
        pass
    if fp:
        fp.write(line + "\n")
        fp.flush()


def find_hwp(root, only):
    out = []
    for dp, dn, fn in os.walk(root):
        rel_dir = os.path.relpath(dp, root)
        top = rel_dir.split(os.sep)[0]
        if top == ADMIN_DIR:
            dn[:] = []
            continue
        if only and not rel_dir.replace(os.sep, "/").startswith(only):
            continue
        for f in fn:
            if f.startswith("~$") or f.startswith("."):
                continue
            if os.path.splitext(f)[1].lower() in (".hwp", ".hwpx"):
                rel = os.path.normpath(os.path.join(rel_dir, f)).replace(os.sep, "/")
                out.append(rel)
    return sorted(out)


def save_json(path, data):
    """MYBOX: '.' 으로 시작하는 임시 파일 금지, 동기화 중 잠김 → tmp- 이름 + 재시도"""
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    tmp = os.path.join(d, "tmp-" + os.path.basename(path))
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    for i in range(10):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            time.sleep(0.5 * (i + 1))
    os.replace(tmp, path)


def copy_retry(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    for i in range(6):
        try:
            shutil.copyfile(src, dst)
            return
        except PermissionError:
            time.sleep(1 + i)
    shutil.copyfile(src, dst)


class Hwp:
    """한글 자동화(HWPFrame.HwpObject) 래퍼"""

    def __init__(self):
        import win32com.client
        self.h = win32com.client.Dispatch("HWPFrame.HwpObject")
        try:
            self.h.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")   # 보안 모듈이 등록돼 있으면 확인 창 생략
        except Exception:
            pass
        try:
            self.h.XHwpWindows.Item(0).Visible = False
        except Exception:
            pass
        try:
            self.h.SetMessageBoxMode(0x2FFF1)     # 한글 알림 창은 자동으로 [확인]/[예]
        except Exception:
            pass

    def convert(self, src, pdf, hwpx):
        fmt = "HWPX" if src.lower().endswith(".hwpx") else "HWP"
        if not self.h.Open(src, fmt, "forceopen:true;versionwarning:false"):
            raise RuntimeError("한글에서 열지 못함")
        try:
            if not self.h.SaveAs(pdf, "PDF", ""):
                raise RuntimeError("PDF 저장 실패")
            if hwpx:
                self.h.SaveAs(hwpx, "HWPX", "")
        finally:
            try:
                self.h.Clear(1)          # 저장하지 않고 닫기
            except Exception:
                pass

    def quit(self):
        try:
            self.h.Quit()
        except Exception:
            pass


def main():
    for stream in (sys.stdout, sys.stderr):              # 한국어 콘솔(cp949)에서 못 찍는 글자는 대체
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--only", default="", help="이 경로로 시작하는 폴더만 (예: 고3 또는 중3/비상)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-hwpx", action="store_true", help="HWPX 사본은 만들지 않음")
    ap.add_argument("--limit", type=int, default=None, help="이번에 변환할 최대 개수")
    args = ap.parse_args()
    root = args.root
    only = args.only.replace("\\", "/").strip("/")

    print("한글 변환기 - 이 창을 닫지 마세요. 끝나면 결과가 나옵니다.\n", flush=True)
    if not os.path.isdir(root):
        print(f"교재 폴더를 찾을 수 없어요: {root}\nMYBOX 가 실행·로그인되어 있는지 확인해 주세요.")
        input("\n엔터를 누르면 닫힙니다…")
        return
    out_root = os.path.join(root, ADMIN_DIR, OUT_DIR)
    manifest_path = os.path.join(out_root, "manifest.json")
    manifest = {}
    if os.path.exists(manifest_path):
        try:
            manifest = json.load(open(manifest_path, encoding="utf-8"))
        except Exception:
            manifest = {}
    os.makedirs(out_root, exist_ok=True)
    logf = open(os.path.join(out_root, f"log_{datetime.datetime.now():%Y%m%d_%H%M}.txt"), "w", encoding="utf-8")

    files = find_hwp(root, only)
    log_line(logf, f"한글 파일 {len(files)}개 찾음 ({root}{' / ' + only if only else ''})")

    todo = []
    for rel in files:
        full = os.path.join(root, *rel.split("/"))
        st = os.stat(full)
        m = manifest.get(rel)
        if m and m.get("status") == "ok" and m.get("size") == st.st_size and m.get("mtime") == int(st.st_mtime) \
                and os.path.exists(conv_pdf_path(root, m["pdf"])):
            continue
        todo.append((rel, st))
    log_line(logf, f"변환할 파일 {len(todo)}개 (이미 변환한 {len(files) - len(todo)}개는 건너뜀)")
    if args.dry_run:
        for rel, _ in todo:
            log_line(logf, "  " + rel)
        input("\n엔터를 누르면 닫힙니다…")
        return
    if not todo:
        input("\n할 일이 없어요. 엔터를 누르면 닫힙니다…")
        return
    if args.limit is None and len(sys.argv) == 1:          # 더블클릭 실행: 처음엔 시험으로 몇 개만 할 수 있게
        ans = input("\n시험으로 5개만 변환하려면 1 을 입력하고 엔터, 전부 변환하려면 그냥 엔터: ").strip()
        if ans == "1":
            args.limit = 5
    if args.limit:
        todo = todo[:args.limit]
        log_line(logf, f"이번에는 {len(todo)}개만 변환합니다.")

    try:
        hwp = Hwp()
    except Exception as ex:
        log_line(logf, f"한글을 실행하지 못했어요. 이 PC 에 한글(정식판)이 설치되어 있는지 확인해 주세요.\n  ({ex})")
        input("\n엔터를 누르면 닫힙니다…")
        return
    log_line(logf, "한글 실행됨. 처음에 '파일 접근 허용' 창이 뜨면 [모두 허용]을 눌러 주세요.\n")

    work = tempfile.mkdtemp(prefix="hwpconv-")
    ok = fail = 0
    t0 = time.time()
    for i, (rel, st) in enumerate(todo, 1):
        full = os.path.join(root, *rel.split("/"))
        stem, ext = os.path.splitext(rel)
        pdf_rel = stem + ".pdf"
        prev = manifest.get(rel, {}).get("pdf")
        if prev:
            pdf_rel = prev                                          # 전에 정한 이름 유지
        elif os.path.exists(os.path.join(root, *pdf_rel.split("/"))):
            pdf_rel = stem + " (한글변환).pdf"                        # 같은 이름의 원래 PDF 가 있으면 피함
        hwpx_rel = f"{ADMIN_DIR}/{OUT_DIR}/hwpx/{stem}.hwpx"
        log_line(logf, f"[{i}/{len(todo)}] {rel}")
        try:
            local_src = os.path.join(work, f"src{i}{ext}")
            local_pdf = os.path.join(work, f"out{i}.pdf")
            local_hwpx = None if args.no_hwpx else os.path.join(work, f"out{i}.hwpx")
            shutil.copyfile(full, local_src)                        # MYBOX 온라인 전용 파일도 여기서 내려받음
            try:
                hwp.convert(local_src, local_pdf, local_hwpx)
            except Exception:
                hwp.quit()                                          # 한글이 멈췄을 수 있으니 새로 띄워 한 번 더
                hwp = Hwp()
                hwp.convert(local_src, local_pdf, local_hwpx)
            if not os.path.exists(local_pdf) or os.path.getsize(local_pdf) < 1000:
                raise RuntimeError("PDF 가 만들어지지 않음")
            copy_retry(local_pdf, conv_pdf_path(root, pdf_rel))
            if local_hwpx and os.path.exists(local_hwpx):
                copy_retry(local_hwpx, os.path.join(root, *hwpx_rel.split("/")))
            manifest[rel] = {"status": "ok", "pdf": pdf_rel, "hwpx": hwpx_rel if local_hwpx else None,
                             "size": st.st_size, "mtime": int(st.st_mtime),
                             "at": datetime.datetime.now().isoformat(timespec="seconds")}
            ok += 1
            log_line(logf, f"    -> {pdf_rel}")
        except Exception as ex:
            fail += 1
            manifest[rel] = {"status": "fail", "error": str(ex)[:300], "size": st.st_size,
                             "mtime": int(st.st_mtime)}
            log_line(logf, f"    X 실패: {ex}")
            logf.write(traceback.format_exc() + "\n")
        finally:
            for p in os.listdir(work):
                try:
                    os.remove(os.path.join(work, p))
                except OSError:
                    pass
        if i % 5 == 0 or i == len(todo):
            save_json(manifest_path, manifest)
    hwp.quit()
    shutil.rmtree(work, ignore_errors=True)
    mins = (time.time() - t0) / 60
    log_line(logf, f"\n끝났어요. 성공 {ok}개, 실패 {fail}개 ({mins:.0f}분)")
    log_line(logf, f"기록: {os.path.join(out_root, 'manifest.json')}")
    if fail:
        log_line(logf, "실패한 파일은 다시 실행하면 한 번 더 시도해요.")
    logf.close()
    input("\n관리자에게 '변환 끝났다'고 알려 주세요. 엔터를 누르면 닫힙니다…")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        input("\n오류로 멈췄어요. 이 화면을 찍어 관리자에게 보내 주세요. 엔터를 누르면 닫힙니다…")
