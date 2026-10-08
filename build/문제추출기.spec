# -*- mode: python ; coding: utf-8 -*-
# 선생님용 exe 두 개를 같은 코드로 만든다:
#   문제추출기.exe       — 평소 쓰는 것 (콘솔 창 없음)
#   문제추출기_진단.exe  — 실행이 안 될 때 원인 확인용 (검은 콘솔 창에 진행 단계·오류가 보임)
# 둘 다 %APPDATA%\문제추출기\log.txt 에 실행 기록을 남긴다 (app_main.py).
# UPX 압축은 끔: 백신 오진·Qt DLL 충돌의 흔한 원인.
import os
from PyInstaller.utils.hooks import collect_data_files

datas = []
datas += collect_data_files('hwpx')
datas += collect_data_files('docx')


a = Analysis(
    ['../app_main.py'],
    pathex=['..'],
    binaries=[],
    datas=datas,
    hiddenimports=['teacher_app'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.Qt3DCore', 'PySide6.QtQuick', 'PySide6.QtQml', 'PySide6.QtMultimedia', 'pytest', 'hwp5', 'winrt', 'rapidocr_onnxruntime', 'onnxruntime', 'cv2'],
    noarchive=False,
    optimize=0,
)
# PATH 에 있던 다른 프로그램(예: Java JDK)의 옛 C 런타임(ucrtbase·api-ms-win-crt)이 딸려 들어오지 않게 뺌.
# Windows 10/11 에는 System32 에 최신판이 있고, 한 프로세스에 C 런타임이 두 개면 문제의 소지가 있다.
a.binaries = [b for b in a.binaries
              if not (os.path.basename(b[0]).lower() == 'ucrtbase.dll'
                      or os.path.basename(b[0]).lower().startswith('api-ms-win-crt-'))]
pyz = PYZ(a.pure)


def make_exe(name, console):
    return EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        [],
        name=name,
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=console,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )


exe = make_exe('문제추출기', False)
exe_diag = make_exe('문제추출기_진단', True)
