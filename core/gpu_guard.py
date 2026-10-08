# -*- coding: utf-8 -*-
"""
일부 PC(예: 인텔 그래픽 최신 드라이버 igd12um64xel.dll)에서 Qt 창이 뜨자마자 강제 종료되는 문제 우회.

원인: Qt 의 Windows 플러그인(qwindows.dll)이 창을 만들 때 그래픽 카드 정보를 보려고
Direct3DCreate9 를 부르는데, 그 PC 의 드라이버가 안에서 C++ 예외를 던져 프로그램이 죽는다
(d3d9 → d3d9on12 → D3D12CreateDevice → 인텔 드라이버 → 처리 안 된 예외 → std::terminate).

우회: qwindows.dll 의 import 표(IAT)에서 Direct3DCreate9 만 "만들지 못함(NULL)" 을 돌려주는 가짜로 바꾼다.
Qt 는 NULL 이면 그냥 넘어가게 되어 있고, 이 앱은 Direct3D 를 쓰지 않는다(화면은 CPU 로 그림).
QApplication 을 만든 뒤(플러그인이 올라온 뒤), 첫 창을 만들기 전에 불러야 한다.
"""
import ctypes
from ctypes import wintypes

_keep = []          # 가짜 함수가 사라지지 않게 붙잡아 둠
_calls = {"n": 0}

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
kernel32.VirtualProtect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]


def _u32(addr):
    return ctypes.c_uint32.from_address(addr).value


def _import_slots(base, dll_name, func_names):
    """모듈(base)의 import 표(IAT)에서 dll_name 의 func_names 슬롯 주소 {이름: 주소}."""
    pe = base + _u32(base + 0x3C)
    opt = pe + 24
    magic = ctypes.c_uint16.from_address(opt).value
    dd = opt + (112 if magic == 0x20B else 96)                   # DataDirectory
    rva = _u32(dd + 1 * 8)                                        # 1 = IMPORT
    out = {}
    if not rva:
        return out
    desc = base + rva
    while True:                                                   # IMAGE_IMPORT_DESCRIPTOR (20바이트)
        int_rva, _ts, _fw, name_rva, iat_rva = (_u32(desc + i * 4) for i in range(5))
        if not name_rva:
            break
        name = ctypes.string_at(base + name_rva).decode("latin-1").lower()
        if name == dll_name.lower():
            int_rva = int_rva or iat_rva
            i = 0
            while True:
                thunk = ctypes.c_uint64.from_address(base + int_rva + i * 8).value
                if not thunk:
                    break
                if not thunk & (1 << 63):                             # 이름으로 가져오는 것
                    fname = ctypes.string_at(base + (thunk & 0x7FFFFFFF) + 2).decode("latin-1")
                    if fname in func_names:
                        out[fname] = base + iat_rva + i * 8
                i += 1
        desc += 20
    return out


def block_d3d9(log=None):
    """qwindows.dll 의 Direct3DCreate9(Ex) 를 가짜로 바꾼다. 바꾼 개수를 돌려준다."""
    log = log or (lambda m: None)
    base = kernel32.GetModuleHandleW("qwindows.dll")
    if not base:
        log("그래픽 우회: qwindows.dll 이 아직 없음 (QApplication 뒤에 불러야 함)")
        return 0
    slots = _import_slots(base, "d3d9.dll", {"Direct3DCreate9", "Direct3DCreate9Ex"})
    n = 0
    for fname, slot in slots.items():
        if fname == "Direct3DCreate9":
            proto = ctypes.WINFUNCTYPE(ctypes.c_void_p, ctypes.c_uint)

            def fake(sdk, _f=fname):
                _calls["n"] += 1
                if _calls["n"] <= 3:
                    log(f"그래픽 우회: Qt 가 {_f} 호출 → 건너뜀")
                return None
        else:
            proto = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_uint, ctypes.c_void_p)

            def fake(sdk, out, _f=fname):
                _calls["n"] += 1
                if _calls["n"] <= 3:
                    log(f"그래픽 우회: Qt 가 {_f} 호출 → 건너뜀")
                return -2005530516                                    # D3DERR_NOTAVAILABLE
        cb = proto(fake)
        _keep.append(cb)
        old = wintypes.DWORD()
        if not kernel32.VirtualProtect(slot, 8, 0x04, ctypes.byref(old)):   # PAGE_READWRITE
            log(f"그래픽 우회: {fname} 슬롯 쓰기 준비 실패 ({ctypes.get_last_error()})")
            continue
        ctypes.c_void_p.from_address(slot).value = ctypes.cast(cb, ctypes.c_void_p).value
        kernel32.VirtualProtect(slot, 8, old.value, ctypes.byref(old))
        n += 1
    log(f"그래픽 우회: d3d9 함수 {n}개 대체 ({', '.join(sorted(slots)) or '대상 없음'})")
    return n
