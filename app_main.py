# -*- coding: utf-8 -*-
"""
문제 추출기 시작 파일 (exe 의 진입점).

무거운 모듈(Qt·PDF 도구)을 불러오기 **전에** 실행 기록을 켠다.
  - 기록 파일: %APPDATA%\\문제추출기\\log.txt  (실행 단계·환경·오류)
  - 치명적 충돌(Qt DLL 등)도 faulthandler 로 같은 파일에 남는다
  - 시작 중 오류는 Windows 기본 메시지 창으로 보여 준다 (Qt 가 안 떠도 보임)
진단용 exe(콘솔 창 있음)도 같은 파일로 만든다.
"""
import datetime
import faulthandler
import os
import platform
import sys
import traceback

LOG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "문제추출기")
LOG_PATH = os.path.join(LOG_DIR, "log.txt")
_log_file = None


def log(msg):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    if sys.stdout is not None:                         # 진단용(콘솔) exe 에서는 화면에도
        try:
            print(line, flush=True)
        except Exception:
            pass
    if _log_file:
        _log_file.write(line + "\n")
        _log_file.flush()


def message_box(title, text):
    """Qt 없이 뜨는 Windows 기본 메시지 창."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
    except Exception:
        pass


DIAG_SHARE = r"N:\개인\내문서\_문제추출_관리\프로그램\진단\결과"     # 결과를 자동으로 올릴 MYBOX 폴더


def diag_wrapper():
    """진단용(콘솔) exe: 시험마다 앱을 자식 프로세스로 돌리고, 앱이 강제 종료돼도 이 창은 남아 결과를 모은다.
    결과(글 + 덤프)는 한 폴더에 모아 MYBOX 진단\\결과 에 자동으로 올린다."""
    import shutil
    import subprocess
    import threading
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    pc = os.environ.get("COMPUTERNAME", "PC")
    out_dir = os.path.join(LOG_DIR, f"진단결과_{pc}_{stamp}")
    os.makedirs(out_dir, exist_ok=True)
    report = open(os.path.join(out_dir, "진단결과.txt"), "w", encoding="utf-8")

    def say(line=""):
        line = line.replace("\0", "")
        try:
            print(line, flush=True)
        except Exception:
            pass
        report.write(line + "\n")
        report.flush()

    say("문제 추출기 진단 모드 - 이 창은 닫지 마세요. (1~2분 걸려요)")
    say("여러 방식으로 창을 띄워 봅니다. 창이 뜨면 저절로 닫혀요.")
    say(f"진단 exe: {sys.executable}")
    known = {"0xC0000005": "메모리 접근 오류(충돌)", "0xC0000409": "스택/보안 검사 실패(충돌)",
             "0xC0000135": "필요한 DLL 없음", "0xC0000142": "DLL 초기화 실패", "0x00000003": "강제 종료(abort)",
             "0xC000041D": "창 처리 중 오류(콜백)", "0xFFFFFFFF": "시간 초과로 멈춤"}
    results = []
    for i, (name, env_add, extra) in enumerate(DIAG_MODES, 1):
        say(f"\n########## 시험 {i}: {name} ##########")
        env = {**os.environ, "PROBLEM_DIAG_PIPE": "1",
               "PROBLEM_DIAG_DUMP": os.path.join(out_dir, f"덤프_{i}.dmp"), **env_add}
        p = subprocess.Popen([sys.executable, "--diag-child", "--diag-autoclose"] + extra + sys.argv[1:], env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        reader = threading.Thread(target=lambda: [say(b.decode("utf-8", errors="replace").rstrip())
                                                  for b in iter(p.stdout.readline, b"")], daemon=True)
        reader.start()
        try:
            code = p.wait(timeout=90)
        except subprocess.TimeoutExpired:
            p.kill()
            code = -1
        reader.join(5)
        hexcode = f"0x{code & 0xFFFFFFFF:08X}"
        results.append((name, code == 0, f"{hexcode} {known.get(hexcode, '')}".strip()))
    say("\n\n=============== 결과 ===============")
    for i, (name, ok, info) in enumerate(results, 1):
        state = "점검" if name.startswith("점검") else ("성공" if ok else "실패")   # 점검 = 일부러 종료시키는 시험
        say(f"  {i}. {state}  {name}   ({info})")
    try:
        from core import diagtools
        n = diagtools.collect_wer(os.path.join(out_dir, "WER"))
        say(f"\nWindows 오류 보고서 {n}개 수거 (WER 폴더)")
    except Exception:
        say("Windows 오류 보고서 수거 실패:\n" + traceback.format_exc())
    say("\n\n=============== PC 정보 ===============")
    try:
        from core import diagtools
        say(diagtools.system_report())
    except Exception:
        say("PC 정보 수집 실패:\n" + traceback.format_exc())
    report.close()
    print("\n결과를 관리자 폴더(MYBOX)에 올리는 중…", flush=True)
    try:
        dest = os.path.join(DIAG_SHARE, os.path.basename(out_dir))
        shutil.copytree(out_dir, dest, dirs_exist_ok=True)
        print(f"\n완료! 결과가 자동으로 올라갔어요:\n  {dest}\n관리자에게 '진단 끝났다'고만 알려 주세요.")
    except Exception as ex:
        print(f"\n자동으로 올리지 못했어요 ({ex}).\n아래 폴더를 통째로 MYBOX '진단' 폴더에 넣어 주세요:\n  {out_dir}")
        try:
            os.startfile(out_dir)
        except Exception:
            pass
    input("\n엔터를 누르면 닫힙니다…")


# 진단 때 차례로 시도하는 방식 (창이 안 뜨는 PC 원인 찾기). 한 번에 한 가지만 바꾼다.
_QPA_LOG = {"QT_LOGGING_RULES": "qt.qpa.*=true"}
DIAG_MODES = [
    # (이름, 환경변수, 추가 인자)
    ("Windows 기본 창 (Qt 없음)", {}, ["--diag-win32=qt,ole"]),
    # 그래픽 우회(core/gpu_guard) 없이 → 문제 PC 에서는 인텔 드라이버 안에서 죽는 것이 정상(대조군)
    ("빈 Qt 창, 그래픽 우회 없이 (대조)", {}, ["--diag-probe=bare", "--diag-nogpuguard"]),
    ("빈 Qt 창, 그래픽 우회", {}, ["--diag-probe=bare"]),
    ("Qt 기본 창 (QWindow), 그래픽 우회", {}, ["--diag-probe=qwindow"]),
    ("전체 창, 그래픽 우회", {}, []),
]


def main():
    global _log_file
    for stream in (sys.stdout, sys.stderr):              # 한국어 콘솔(cp949)에서 못 찍는 글자는 대체
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    is_diag_exe = "진단" in os.path.basename(sys.executable)      # 진단용 exe 만 감싸는 모드
    if is_diag_exe and "--diag-child" not in sys.argv:
        diag_wrapper()
        return
    if "--diag-child" in sys.argv:
        sys.argv.remove("--diag-child")
    if os.environ.get("PROBLEM_DIAG_PIPE"):              # 진단 자식: 출력이 파이프로 감 → UTF-8 로
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass
    plain = "--diag-plain" in sys.argv                   # 진단: 기록 장치(faulthandler) 없이
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        if os.path.exists(LOG_PATH) and os.path.getsize(LOG_PATH) > 2_000_000:
            os.replace(LOG_PATH, LOG_PATH + ".old")
        _log_file = open(LOG_PATH, "a", encoding="utf-8")
        # 치명적 충돌(Qt 내부 등) 위치: 진단용(콘솔)은 화면에, 평소 exe 는 기록 파일에
        if not plain:
            faulthandler.enable(sys.stderr if sys.stderr is not None else _log_file, all_threads=True)
    except Exception:
        _log_file = None

    log("=" * 60)
    log(f"시작: {sys.executable}")
    log(f"Windows: {platform.platform()} / {platform.version()}  64bit={sys.maxsize > 2**32}")
    log(f"Python {platform.python_version()}  임시폴더={getattr(sys, '_MEIPASS', '-')}")
    log(f"인자: {sys.argv[1:]}")
    if os.environ.get("PROBLEM_DIAG_DUMP"):              # 진단 자식: 강제 종료 순간 스택·DLL·덤프 기록
        try:
            from core import diagtools
            diagtools.install_abort_hooks(log, os.environ["PROBLEM_DIAG_DUMP"])
        except Exception:
            log("강제 종료 포착 장치 설치 실패:\n" + traceback.format_exc())
    if "--diag-test-abort" in sys.argv:                  # 포착 장치 점검: Python·Qt 가 쓰는 C 런타임으로 abort
        from core import diagtools
        diagtools.system_ucrt().abort()
    if "--diag-noext" in sys.argv:                       # 진단: 외부 훅·DLL 끼어들기 차단 (Qt 불러오기 전에)
        from core import diagtools
        diagtools.disable_extension_points(log)
    win32 = next((a for a in sys.argv if a.startswith("--diag-win32")), None)
    if win32:                                            # 진단: Qt 없이 Windows 기본 창만
        from core import diagtools
        opts = win32.partition("=")[2].split(",")
        mods = diagtools.foreign_modules()
        log(f"끼어든 DLL {len(mods)}개 (Microsoft·앱 것 제외): " + (" | ".join(mods) if mods else "없음"))
        ok = diagtools.win32_window_test(log, qt_like="qt" in opts, ole="ole" in opts)
        new = [m for m in diagtools.foreign_modules() if m not in mods]
        if new:
            log("창을 띄운 뒤 새로 끼어든 DLL: " + " | ".join(new))
        sys.exit(0 if ok else 1)
    if "--diag-noime" in sys.argv:                       # 진단: 이 프로세스의 입력기(IME) 끔 — 창 만들기 전에
        import ctypes
        log(f"입력기 끔: ImmDisableIME → {ctypes.WinDLL('imm32').ImmDisableIME(ctypes.c_uint32(0xFFFFFFFF))}")
    # 창이 뜨기 전에 멈춘 실행 기록 (다음 실행 기록에 남김). 예전 '안전 모드' 표시는 원인(그래픽 드라이버,
    # core/gpu_guard.py)을 찾아 필요 없어졌으므로 지운다.
    pending = os.path.join(LOG_DIR, "start_pending")
    no_gui_check = "--diag-autoclose" in sys.argv or "--selftest" in sys.argv   # 진단·자가점검은 표시 안 남김
    if not no_gui_check:
        try:
            old_safe = os.path.join(LOG_DIR, "safe_mode")
            if os.path.exists(old_safe):
                os.remove(old_safe)
                log("예전 안전 모드 표시 삭제")
            if os.path.exists(pending):
                log("지난 실행은 창을 띄우기 전에 멈췄음")
            open(pending, "w").close()
        except OSError:
            pass

    def on_shown():
        try:
            if os.path.exists(pending):
                os.remove(pending)
        except OSError:
            pass
    try:
        log("모듈 불러오는 중 (Qt·PDF)…")
        import teacher_app
        log("모듈 불러오기 완료 → 창 띄우는 중")
        teacher_app.main(log, on_shown)
        log("정상 종료")
    except SystemExit as ex:
        log(f"종료 코드 {ex.code}")
        raise
    except BaseException:
        tb = traceback.format_exc()
        log("오류로 멈춤:\n" + tb)
        message_box("문제 추출기 — 시작 오류",
                    "프로그램을 시작하지 못했어요.\n\n"
                    f"{tb[-1500:]}\n\n기록 파일: {LOG_PATH}\n이 파일을 관리자에게 보내 주세요.")
        if sys.stdout is not None:
            input("\n엔터를 누르면 닫힙니다…")
        sys.exit(1)


if __name__ == "__main__":
    main()
