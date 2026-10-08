# -*- coding: utf-8 -*-
"""
창이 안 뜨는 PC 원인 찾기용 (Qt 없이 동작).

  all_modules()        이 프로세스에 들어와 있는 DLL 전부 (경로·제조사·버전)
  foreign_modules()    그중 Microsoft·Python·Qt 기본이 아닌 것
  win32_window_test()  Qt 를 거치지 않고 Windows 기본 API 로 빈 창을 띄워 본다
                       (qt_like=True: Qt 와 같은 조건 — 모니터별 배율·아이콘·창 모양, ole=True: OLE/COM 초기화까지)
  install_abort_hooks()  누군가 abort()/terminate()/purecall 을 부르면 그 순간의 호출 스택(모듈+오프셋)·
                         전체 모듈 목록을 기록하고 덤프 파일을 남긴다
"""
import ctypes
import os
import sys
import time
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.GetModuleHandleExW.argtypes = [wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(wintypes.HMODULE)]
kernel32.GetModuleFileNameW.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
kernel32.RtlCaptureStackBackTrace.restype = ctypes.c_ushort
kernel32.RtlCaptureStackBackTrace.argtypes = [wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p),
                                              ctypes.c_void_p]
kernel32.CreateFileW.restype = wintypes.HANDLE
kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                 wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


# ---------------------------------------------------------------- 모듈 목록
def _file_info(path):
    """(제조사, 파일 버전) — 버전 정보가 없으면 빈 문자열."""
    try:
        ver = ctypes.WinDLL("version")
        size = ver.GetFileVersionInfoSizeW(path, None)
        if not size:
            return "", ""
        buf = ctypes.create_string_buffer(size)
        if not ver.GetFileVersionInfoW(path, 0, size, buf):
            return "", ""
        ptr, ln = ctypes.c_void_p(), wintypes.UINT()
        lang = "040904b0"
        if ver.VerQueryValueW(buf, "\\VarFileInfo\\Translation", ctypes.byref(ptr), ctypes.byref(ln)) and ln.value >= 4:
            w = (ctypes.c_ushort * 2).from_address(ptr.value)
            lang = f"{w[0]:04x}{w[1]:04x}"
        out = []
        for key in ("CompanyName", "FileVersion"):
            if ver.VerQueryValueW(buf, f"\\StringFileInfo\\{lang}\\{key}", ctypes.byref(ptr), ctypes.byref(ln)) and ln.value:
                out.append(ctypes.wstring_at(ptr.value, ln.value).rstrip("\0").strip())
            else:
                out.append("")
        return out[0], out[1]
    except Exception:
        return "", ""


def all_modules():
    """[(경로, 제조사, 버전)] — 필터 없이 전부."""
    psapi = ctypes.WinDLL("psapi")
    psapi.EnumProcessModulesEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD,
                                           ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    psapi.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    proc = kernel32.GetCurrentProcess()
    arr = (wintypes.HMODULE * 4096)()
    needed = wintypes.DWORD()
    if not psapi.EnumProcessModulesEx(proc, arr, ctypes.sizeof(arr), ctypes.byref(needed), 3):
        return []
    n = min(needed.value // ctypes.sizeof(wintypes.HMODULE), 4096)
    buf = ctypes.create_unicode_buffer(1024)
    out = []
    for i in range(n):
        if arr[i] and psapi.GetModuleFileNameExW(proc, arr[i], buf, 1024):
            out.append((buf.value,) + _file_info(buf.value))
    return out


def _is_ours(path, company):
    pl = path.lower()
    meipass = (getattr(sys, "_MEIPASS", "") or "").lower()
    windir = os.environ.get("WINDIR", r"C:\Windows").lower()
    return ("microsoft" in company.lower() or (meipass and pl.startswith(meipass))
            or (pl.startswith(windir) and company == "The ICU Project")      # Windows 기본 포함 ICU
            or pl == sys.executable.lower())


def foreign_modules():
    """Microsoft 제품·exe 에 들어 있는 것(Python·Qt)을 뺀 DLL (Windows 폴더 안이라도 다른 회사면 보임)."""
    return [f"{p} [{c or '제조사 없음'} {v}]".strip() for p, c, v in all_modules() if not _is_ours(p, c)]


def module_report():
    """전체 모듈 목록 글. Microsoft·exe 것이 아니면 ★."""
    lines = []
    for p, c, v in all_modules():
        lines.append(f"  {'  ' if _is_ours(p, c) else '★'} {p}  [{c}] {v}")
    return "\n".join(lines)


# ---------------------------------------------------------------- 주소 → 모듈+오프셋(+함수 이름)
_sym_ready = False


def _symbolize(addr):
    global _sym_ready
    h = wintypes.HMODULE()
    name = "?"
    if kernel32.GetModuleHandleExW(0x6, ctypes.c_void_p(addr), ctypes.byref(h)) and h.value:   # FROM_ADDRESS|UNCHANGED
        buf = ctypes.create_unicode_buffer(1024)
        kernel32.GetModuleFileNameW(h, buf, 1024)
        name = f"{os.path.basename(buf.value)}+0x{addr - h.value:x}"
    try:
        dbg = ctypes.WinDLL("dbghelp")
        proc = kernel32.GetCurrentProcess()
        if not _sym_ready:
            dbg.SymInitializeW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.BOOL]
            dbg.SymSetOptions(0x2 | 0x4)                                  # UNDNAME | DEFERRED_LOADS
            dbg.SymInitializeW(proc, None, True)
            _sym_ready = True
        size = 88 + 512 * 2
        raw = ctypes.create_string_buffer(size)
        ctypes.c_ulong.from_buffer(raw, 0).value = 88                      # SizeOfStruct
        ctypes.c_ulong.from_buffer(raw, 80).value = 512                    # MaxNameLen
        disp = ctypes.c_ulonglong()
        dbg.SymFromAddrW.argtypes = [wintypes.HANDLE, ctypes.c_ulonglong, ctypes.POINTER(ctypes.c_ulonglong),
                                     ctypes.c_void_p]
        if dbg.SymFromAddrW(proc, addr, ctypes.byref(disp), raw):
            ln = ctypes.c_ulong.from_buffer(raw, 76).value                 # NameLen
            sym = ctypes.wstring_at(ctypes.addressof(raw) + 84, ln)
            name += f"  ({sym}+0x{disp.value:x})"
    except Exception as ex:
        name += f"  (이름 풀이 실패: {ex})"
    return name


def stack_report(skip=0):
    try:                                                   # 이름 풀이 준비 + 그 뒤 불러온 DLL 반영
        _symbolize(0)
        dbg = ctypes.WinDLL("dbghelp")
        dbg.SymRefreshModuleList.argtypes = [wintypes.HANDLE]
        dbg.SymRefreshModuleList(kernel32.GetCurrentProcess())
    except Exception:
        pass
    frames = (ctypes.c_void_p * 62)()
    n = kernel32.RtlCaptureStackBackTrace(skip, 62, frames, None)
    return "\n".join(f"  #{i:02d} 0x{(frames[i] or 0):016x}  {_symbolize(frames[i] or 0)}" for i in range(n))


# ---------------------------------------------------------------- abort 순간 기록
_hooks = []          # ctypes 콜백이 사라지지 않게 붙잡아 둠
_seen = {"why": None}


def system_ucrt():
    """Python·Qt 가 실제로 쓰는 System32 의 C 런타임. 이름만으로 열면 exe 에 딸려 온 다른 사본이 열릴 수 있다."""
    sysdir = ctypes.create_unicode_buffer(260)
    kernel32.GetSystemDirectoryW(sysdir, 260)
    return ctypes.CDLL(os.path.join(sysdir.value, "ucrtbase.dll"))


def disable_extension_points(log):
    """이 프로세스에 전역 훅·AppInit DLL·옛 입력기 DLL 이 끼어드는 것을 막는다 (Windows 보안 정책)."""
    flags = wintypes.DWORD(1)
    ok = kernel32.SetProcessMitigationPolicy(6, ctypes.byref(flags), 4)    # ProcessExtensionPointDisablePolicy
    log(f"외부 확장 차단 (ExtensionPointDisable) → {'성공' if ok else f'실패 {ctypes.get_last_error()}'}")


_MSG_NAMES = {0x1: "WM_CREATE", 0x2: "WM_DESTROY", 0x3: "WM_MOVE", 0x5: "WM_SIZE", 0x6: "WM_ACTIVATE",
              0x7: "WM_SETFOCUS", 0x8: "WM_KILLFOCUS", 0xC: "WM_SETTEXT", 0xD: "WM_GETTEXT", 0xE: "WM_GETTEXTLENGTH",
              0x18: "WM_SHOWWINDOW", 0x1A: "WM_SETTINGCHANGE", 0x1C: "WM_ACTIVATEAPP", 0x24: "WM_GETMINMAXINFO",
              0x3D: "WM_GETOBJECT", 0x46: "WM_WINDOWPOSCHANGING", 0x47: "WM_WINDOWPOSCHANGED",
              0x7F: "WM_GETICON", 0x80: "WM_SETICON", 0x81: "WM_NCCREATE", 0x82: "WM_NCDESTROY",
              0x83: "WM_NCCALCSIZE", 0x84: "WM_NCHITTEST", 0x85: "WM_NCPAINT", 0x86: "WM_NCACTIVATE",
              0x281: "WM_IME_SETCONTEXT", 0x282: "WM_IME_NOTIFY", 0x2E0: "WM_DPICHANGED",
              0x2E3: "WM_DPICHANGED_AFTERPARENT", 0x2E4: "WM_GETDPISCALEDSIZE", 0x31F: "WM_DWMNCRENDERINGCHANGED",
              0x320: "WM_DWMCOLORIZATIONCOLORCHANGED", 0x31A: "WM_THEMECHANGED", 0x14: "WM_ERASEBKGND",
              0xF: "WM_PAINT", 0x20: "WM_SETCURSOR", 0x21: "WM_MOUSEACTIVATE", 0x2A1: "WM_MOUSEHOVER"}


def install_msg_hook(log):
    """이 스레드의 창 프로시저로 가는 모든 메시지를 '처리 전에' 기록 (죽기 직전 메시지 = 범인 후보)."""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    user32.CallNextHookEx.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
    user32.CallNextHookEx.restype = ctypes.c_ssize_t
    user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
    user32.SetWindowsHookExW.restype = wintypes.HANDLE

    class CWPSTRUCT(ctypes.Structure):
        _fields_ = [("lParam", wintypes.LPARAM), ("wParam", wintypes.WPARAM), ("message", wintypes.UINT),
                    ("hwnd", wintypes.HWND)]
    state = {"hook": None}

    def proc(code, wp, lp):
        if code >= 0:
            try:
                m = CWPSTRUCT.from_address(lp)
                log(f"  [메시지] hwnd=0x{(m.hwnd or 0):x} 0x{m.message:04X} {_MSG_NAMES.get(m.message, '')} "
                    f"wp=0x{m.wParam:x} lp=0x{m.lParam & 0xFFFFFFFFFFFFFFFF:x}")
            except Exception:
                pass
        return user32.CallNextHookEx(state["hook"], code, wp, lp)
    cb = HOOKPROC(proc)
    _hooks.append(cb)
    state["hook"] = user32.SetWindowsHookExW(4, cb, None, kernel32.GetCurrentThreadId())   # WH_CALLWNDPROC
    log(f"메시지 기록 장치 {'설치됨' if state['hook'] else f'설치 실패 {ctypes.get_last_error()}'}")
    if state["hook"]:                                   # Python 이 정리된 뒤 콜백이 불리면 충돌 → 끝날 때 뗌
        import atexit
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HANDLE]
        atexit.register(user32.UnhookWindowsHookEx, state["hook"])
    return state


def collect_wer(dest, keyword="문제추출기", days=14):
    """Windows 오류 보고(Report.wer: 죽는 순간 불러와 있던 DLL 목록 포함) 중 이 앱 것을 dest 로 복사. 복사한 개수."""
    import shutil
    roots = [os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\Windows\WER"),
             os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), r"Microsoft\Windows\WER")]
    n = 0
    limit = time.time() - days * 86400
    for root in roots:
        for sub in ("ReportArchive", "ReportQueue"):
            base = os.path.join(root, sub)
            try:
                dirs = os.listdir(base)
            except OSError:
                continue
            for d in dirs:
                src = os.path.join(base, d)
                try:
                    if os.path.getmtime(src) < limit:
                        continue
                    for f in os.listdir(src):
                        p = os.path.join(src, f)
                        if not f.lower().endswith(".wer"):
                            continue
                        raw = open(p, "rb").read()
                        text = raw.decode("utf-16", errors="replace") if raw[:2] == b"\xff\xfe" else raw.decode("utf-8", "replace")
                        if keyword not in text and keyword not in d:
                            continue
                        os.makedirs(os.path.join(dest, d), exist_ok=True)
                        shutil.copy2(p, os.path.join(dest, d, f))
                        n += 1
                except OSError:
                    continue
    return n


def write_dump(path):
    try:
        dbg = ctypes.WinDLL("dbghelp")
        dbg.MiniDumpWriteDump.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.HANDLE, wintypes.DWORD,
                                          ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
        h = kernel32.CreateFileW(path, 0x40000000, 0, None, 2, 0x80, None)   # GENERIC_WRITE, CREATE_ALWAYS
        if not h or h == wintypes.HANDLE(-1).value:
            return False
        # DataSegs | HandleData | UnloadedModules | IndirectlyReferencedMemory | ProcessThreadData | ThreadInfo
        ok = dbg.MiniDumpWriteDump(kernel32.GetCurrentProcess(), os.getpid(), h,
                                   0x1 | 0x4 | 0x20 | 0x40 | 0x100 | 0x1000, None, None, None)
        kernel32.CloseHandle(h)
        return bool(ok)
    except Exception:
        return False


def install_abort_hooks(log, dump_path=None):
    """abort()/std::terminate/순수 가상 함수 호출/잘못된 인자 → 이유·호출 스택·모듈 목록·덤프 기록.
    faulthandler.enable() 뒤에 불러야 SIGABRT 처리를 이쪽이 가져온다."""
    import faulthandler
    ucrt = system_ucrt()
    buf = ctypes.create_unicode_buffer(1024)
    kernel32.GetModuleFileNameW(ucrt._handle, buf, 1024)
    log(f"포착 장치를 걸 C 런타임: {buf.value}")
    ucrt.signal.restype = ctypes.c_void_p
    ucrt.signal.argtypes = [ctypes.c_int, ctypes.c_void_p]

    def report(why):
        if _seen["why"]:
            return
        _seen["why"] = why
        try:
            log(f"!!!!! 강제 종료 포착: {why}")
            log("호출 스택 (위가 가장 최근, 모듈+오프셋):\n" + stack_report(1))
            if dump_path:
                log(f"덤프 파일: {dump_path} → {'저장됨' if write_dump(dump_path) else '저장 실패'}")
            try:
                faulthandler.dump_traceback(sys.stderr if sys.stderr is not None else sys.__stderr__, all_threads=True)
            except Exception:
                pass
            log("그 순간 불러와 있던 DLL 전체 (★ = Microsoft·앱 것이 아님):\n" + module_report())
        except Exception as ex:
            log(f"강제 종료 기록 중 오류: {ex}")

    SIGHANDLER = ctypes.CFUNCTYPE(None, ctypes.c_int)
    VOIDFN = ctypes.CFUNCTYPE(None)
    INVPARAM = ctypes.CFUNCTYPE(None, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint,
                                ctypes.c_size_t)

    def on_abort(sig):
        report("abort() 호출 (SIGABRT)")
        ucrt._exit(3)

    def on_terminate():
        report("std::terminate 호출 (처리 안 된 C++ 예외 등)")
        ucrt._exit(3)

    def on_purecall():
        report("순수 가상 함수 호출 (_purecall)")
        ucrt._exit(3)

    def on_invalid(expr, func, file, line, _r):
        report(f"CRT 잘못된 인자 ({func} {expr} {file}:{line})")
        ucrt._exit(3)

    cbs = [SIGHANDLER(on_abort), VOIDFN(on_terminate), VOIDFN(on_purecall), INVPARAM(on_invalid)]
    _hooks.extend(cbs)
    ucrt.signal(22, ctypes.cast(cbs[0], ctypes.c_void_p))                   # SIGABRT
    for fn, cb in (("set_terminate", cbs[1]), ("_set_purecall_handler", cbs[2]),
                   ("_set_invalid_parameter_handler", cbs[3])):
        try:
            f = getattr(ucrt, fn)
            f.restype = ctypes.c_void_p
            f.argtypes = [ctypes.c_void_p]
            f(ctypes.cast(cb, ctypes.c_void_p))
        except Exception as ex:
            log(f"{fn} 설치 실패: {ex}")
    log("강제 종료 포착 장치 설치됨" + (f" (덤프: {dump_path})" if dump_path else ""))


# ---------------------------------------------------------------- Windows 기본 창
def win32_window_test(log, seconds=1.5, qt_like=False, ole=False):
    """Windows 기본 창 띄우기. 성공하면 True.
    qt_like: Qt 와 같은 조건 (모니터별 배율 v2, 더블클릭 클래스 + 아이콘, 스타일 0x86CF0000)
    ole: Qt 처럼 먼저 OleInitialize (입력기 TSF 등이 COM 위에서 붙는 경로)"""
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    if qt_like:
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        ok = user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))     # PER_MONITOR_AWARE_V2
        log(f"Windows 기본 창: 모니터별 배율 v2 설정 {'성공' if ok else '실패'}")
    if ole:
        hr = ctypes.WinDLL("ole32").OleInitialize(None)
        log(f"Windows 기본 창: OleInitialize → 0x{hr & 0xFFFFFFFF:08X}")
    WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
    user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t
    user32.LoadIconW.restype = wintypes.HICON
    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
    user32.LoadCursorW.restype = wintypes.HANDLE
    user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]

    def wndproc(h, m, w, l):
        return user32.DefWindowProcW(h, m, w, l)
    proc = WNDPROC(wndproc)

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [("style", wintypes.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                    ("cbWndExtra", ctypes.c_int), ("hInstance", wintypes.HINSTANCE), ("hIcon", wintypes.HICON),
                    ("hCursor", wintypes.HANDLE), ("hbrBackground", wintypes.HBRUSH),
                    ("lpszMenuName", wintypes.LPCWSTR), ("lpszClassName", wintypes.LPCWSTR)]
    hinst = kernel32.GetModuleHandleW(None)
    cls = "ProbeWin32Class"
    if qt_like:
        wc = WNDCLASSW(0x8, proc, 0, 0, hinst, user32.LoadIconW(None, ctypes.c_void_p(32512)),
                       user32.LoadCursorW(None, ctypes.c_void_p(32512)), None, None, cls)
        style = 0x86CF0000
    else:
        wc = WNDCLASSW(0, proc, 0, 0, hinst, None, None, ctypes.c_void_p(6), None, cls)
        style = 0x10CF0000
    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    if not user32.RegisterClassW(ctypes.byref(wc)):
        log(f"Windows 기본 창: 클래스 등록 실패 (오류 {ctypes.get_last_error()})")
        return False
    user32.CreateWindowExW.restype = wintypes.HWND
    user32.CreateWindowExW.argtypes = [wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD,
                                       ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                       wintypes.HWND, wintypes.HMENU, wintypes.HINSTANCE, wintypes.LPVOID]
    log("Windows 기본 창: CreateWindowEx 호출")
    hwnd = user32.CreateWindowExW(0, cls, "진단 - Windows 기본 창", style,
                                  100, 100, 393, 297, None, None, hinst, None)
    if not hwnd:
        log(f"Windows 기본 창: 만들기 실패 (오류 {ctypes.get_last_error()})")
        return False
    log("Windows 기본 창: 만들어짐")
    user32.ShowWindow(hwnd, 5)
    user32.UpdateWindow(hwnd)
    log("Windows 기본 창: 표시됨")
    msg = wintypes.MSG()
    end = time.time() + seconds
    while time.time() < end:
        while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        time.sleep(0.02)
    user32.DestroyWindow(hwnd)
    log("Windows 기본 창: 정상 종료")
    return True


# ---------------------------------------------------------------- PC 정보
def system_report():
    import subprocess
    import winreg
    out = []
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        vals = {}
        for name in ("ProductName", "EditionID", "DisplayVersion", "CurrentBuild", "UBR"):
            try:
                vals[name] = winreg.QueryValueEx(k, name)[0]
            except OSError:
                pass
        out.append("Windows: " + " / ".join(f"{a}={b}" for a, b in vals.items()))
    except OSError as ex:
        out.append(f"Windows 정보 실패: {ex}")
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\WindowsSelfHost\Applicability")
        out.append(f"참가자(Insider) 채널: {winreg.QueryValueEx(k, 'BranchName')[0]}")
    except OSError:
        out.append("참가자(Insider) 채널: 없음")
    try:
        user32 = ctypes.WinDLL("user32")
        arr = (ctypes.c_void_p * 32)()
        n = user32.GetKeyboardLayoutList(32, arr)
        out.append("키보드 배열: " + ", ".join(f"{(arr[i] or 0) & 0xFFFFFFFF:08X}" for i in range(n)))
    except Exception:
        pass
    try:
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop\WindowMetrics")
        out.append(f"화면 배율(AppliedDPI): {winreg.QueryValueEx(k, 'AppliedDPI')[0]}")
    except OSError:
        pass

    def run(cmd):
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=60, creationflags=0x08000000)
            return r.stdout.decode("mbcs", errors="replace").strip()
        except Exception as ex:
            return f"(실행 실패: {ex})"
    out.append("\n----- 실행 중인 프로그램 -----\n" + run(["tasklist", "/fo", "table"]))
    q = "*[System[(Level=1 or Level=2) and TimeCreated[timediff(@SystemTime) <= 1209600000]]]"
    out.append("\n----- 이벤트 뷰어: 최근 2주 응용 프로그램 오류 (최신 40개) -----\n"
               + run(["wevtutil", "qe", "Application", "/c:40", "/rd:true", "/f:text", f"/q:{q}"]))
    return "\n".join(out)
