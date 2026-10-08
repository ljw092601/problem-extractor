@echo off
rem 선생님용 프로그램(문제추출기.exe) 다시 만들기. 결과: build\dist\문제추출기.exe
rem 필요: pip install --user PySide6 pyinstaller PyMuPDF python-docx python-hwpx
chcp 65001 > nul
cd /d "%~dp0"
python -m PyInstaller --noconfirm build\문제추출기.spec --distpath build\dist --workpath build\work
if errorlevel 1 (
  echo 실패했습니다. 위 메시지를 확인하세요.
  exit /b 1
)
echo.
echo 점검 실행 중...
build\dist\문제추출기.exe --root "%~dp0테스트_자료폴더" --selftest "%TEMP%\문제추출기_점검"
type "%TEMP%\문제추출기_점검\selftest.txt"
echo.
echo 완료: build\dist\문제추출기.exe
