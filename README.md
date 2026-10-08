# 문제 추출기 (problem-extractor)

학원 내부용 도구. 관리자가 미리 등록한 교재 PDF에서 선생님이 원하는 문제만 골라
학원 양식(2단)에 맞춘 docx / hwpx / pdf 로 뽑아낸다.

자세한 설계·규칙은 [PLAN.md](PLAN.md), 교재 등록 작업 절차는 [work/AGENT_GUIDE.md](work/AGENT_GUIDE.md) 참고.

## 구성

| 파일 | 역할 |
|---|---|
| `app_main.py` | exe 진입점 (실행 기록 → GUI 시작) |
| `teacher_app.py` | 선생님용 GUI (PySide6) |
| `admin.py` | 관리자 명령줄 도구 (scan / register / approve / exclude …) |
| `book_tool.py` | 교재 등록 작업 도구 (좌표 잡기, 추출, OCR) |
| `core/` | 공통 로직 — 추출(`extract.py`), 등록 기록(`registry.py`), 교재/단원(`books.py`), GPU 우회(`gpu_guard.py`) 등 |
| `build_docx.py` / `build_hwpx.py` / `build_pdf.py` | 선택한 문제를 2단 문서로 조립 |
| `template.py`, `수.hwp` | 학원 양식 규격 |
| `hwp_convert.py` | 한글 파일 → PDF 변환기 (한글 설치 PC 전용) |
| `work/<학년>_<교재>/` | 교재별 좌표(`layout.json`, `problems.json`), 단원(`units.json`), 작업 메모 |
| `build/*.spec` | PyInstaller 설정, `make_exe.bat` 로 빌드 |
| `tests/` | pytest + GUI 스모크 테스트 |

## 설치 / 실행

```bat
pip install -r requirements.txt
python app_main.py --root "N:\개인\내문서"
```

exe 빌드: `make_exe.bat` → `build\dist\문제추출기.exe`

## 저장소에 없는 것

교재 PDF 원본, 렌더링된 쪽 이미지(`sheets/*.png`), 빌드 산출물(`build/dist`, `build/venv*`)은
용량·저작권 때문에 올리지 않는다. 교재 원본은 MYBOX `N:\개인\내문서` 기준이며
로컬 사본 대응표는 `work/_src/sources.json` 에 있다.
