# -*- coding: utf-8 -*-
"""
선생님용 앱 자동 점검 (화면 없이 실행 가능):
    set QT_QPA_PLATFORM=offscreen
    python tests/gui_smoke.py <교재 폴더> <결과·캡처 저장 폴더>

교재 목록 → 사용 가능 교재 열기 → 문제 5개 담기 → docx/pdf/hwpx 만들기까지 진행하고
단계별 화면 캡처(PNG)를 남긴다. 설정 파일은 결과 폴더 안에만 쓴다(실제 PC 설정 안 건드림).
"""
import os
import sys
import time

ROOT, OUT = sys.argv[1], sys.argv[2]
os.makedirs(OUT, exist_ok=True)
os.environ["APPDATA"] = OUT                                  # 설정 파일을 결과 폴더에
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402

import teacher_app as A  # noqa: E402
from core import registry as R  # noqa: E402

messages = []
QMessageBox.exec = lambda self: messages.append(self.text()) or 0
QMessageBox.information = staticmethod(lambda *a, **k: messages.append(a[2]) or 0)
QMessageBox.warning = staticmethod(lambda *a, **k: messages.append(a[2]) or 0)

app = QApplication(sys.argv)
app.setFont(QFont("Malgun Gothic", 10))
win = A.MainWindow(root=ROOT)
win.out_dir = OUT
win.show()


def wait(cond, timeout=60, what=""):
    t = time.time()
    while not cond():
        app.processEvents()
        time.sleep(0.02)
        if time.time() - t > timeout:
            raise SystemExit(f"시간 초과: {what}  (메시지: {messages})")
    app.processEvents()


def shot(name):
    app.processEvents()
    win.grab().save(os.path.join(OUT, name))


win.start()
wait(lambda: hasattr(win, "books"), what="교재 목록")
ready = [rel for rel, st in win.books if st == R.READY]
print("교재:", len(win.books), "사용 가능:", ready)
assert ready, "사용 가능한 교재가 없음"
shot("1_목록.png")

def thumbs_done(rel):
    return all((rel, pid) in win.thumbs for pid in win.grid_items)


win.open(ready[-1])
wait(lambda: win.pick_all_btn.isEnabled(), what="교재 열기")
wait(lambda: thumbs_done(ready[-1]), what="썸네일")
print("문제 수:", len(win.problems), "묶음:", [g["title"] for g in win.groups])
for i in (0, 2, 1, 4, 3):                                   # 순서 섞어서 클릭
    win.on_problem_click(win.grid.item(i))
shot("2_담기.png")

if len(ready) > 1:                                          # 다른 교재(단원 있음) 문제도 섞기
    win.open(ready[0])
    wait(lambda: win.pick_all_btn.isEnabled(), what="두 번째 교재")
    wait(lambda: thumbs_done(ready[0]), what="썸네일2")
    print("단원:", [(g["title"], len(g["problems"])) for g in win.groups])
    win.on_problem_click(win.grid.item(0))
    if len(win.groups) > 1:                                 # 두 번째 단원으로 옮겨 번호로 담기
        win.show_group(1)
        wait(lambda: thumbs_done(ready[0]), what="단원2 썸네일")
        nums = [p["num"] for p in win.groups[1]["problems"]]
        win.num_edit.setText(f"{nums[0]}-{nums[2]}, 999")
        win.pick_by_numbers()
        print("번호로 담기 후:", len(win.picks), "메시지:", messages[-1].splitlines()[-1] if messages else None)
    shot("3_단원.png")

win.name_edit.setText("점검_학습지")
for cb in win.fmt_boxes.values():
    cb.setChecked(True)
win.make()
wait(lambda: not win.busy, timeout=180, what="만들기")
shot("4_완료.png")
made = sorted(n for n in os.listdir(OUT) if n.startswith("점검_학습지"))
print("만든 파일:", made)
print("메시지:", [m.splitlines()[0] for m in messages])
assert len(made) == 3, made
assert len(win.picks) == 5 + 1 + 3 or len(ready) == 1, win.picks
print("OK")
