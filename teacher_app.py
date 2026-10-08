# -*- coding: utf-8 -*-
"""
문제 추출기 — 선생님용 프로그램.

    교재 폴더(MYBOX)에서 관리자가 등록한 교재를 골라, 문제를 클릭해 담고,
    학원 양식(2단, 한 쪽 4문제)의 Word / PDF / 한글 파일로 저장한다.

    - 교재 폴더와 관리 기록은 읽기만 한다 (쓰지 않음).
    - 결과 파일은 이 PC(기본: 바탕화면)에 저장한다.

실행:  python teacher_app.py [--root <교재 폴더>]
"""
import argparse
import json
import os
import shutil
import sys
import time
import traceback

import fitz
from PySide6.QtCore import (QAbstractNativeEventFilter, QObject, QRunnable, QSize, Qt, QThreadPool, QTimer,
                            QUrl, Signal, qInstallMessageHandler, qVersion)
from PySide6.QtGui import QBrush, QColor, QDesktopServices, QFont, QIcon, QImage, QPixmap, QWindow
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPushButton, QRadioButton,
    QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

import build_docx
import build_hwpx
import build_pdf
import selector
from core import books
from core import registry as R
from core.pdfpage import ready_page

APP_NAME = "문제 추출기"
LOG = lambda m: None                  # app_main.py 가 실행 기록 함수로 바꿔 끼운다
DEFAULT_ROOT = r"N:\개인\내문서"
THUMB_DPI = 72
FORMATS = [("docx", "Word (.docx)", build_docx), ("pdf", "PDF (.pdf)", build_pdf),
           ("hwpx", "한글 (.hwpx)", build_hwpx)]

GRAY = QColor("#9a9a9a")
PICKED_BG = QColor("#dbe9ff")
ROLE_REL = Qt.UserRole
ROLE_PID = Qt.UserRole + 1


# ---------------------------------------------------------------- 설정 (이 PC 에만 저장)

def config_path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "문제추출기", "config.json")


def load_config():
    try:
        with open(config_path(), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_config(cfg):
    p = config_path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1)


def desktop_dir():
    d = os.path.join(os.path.expanduser("~"), "Desktop")
    return d if os.path.isdir(d) else os.path.expanduser("~")


# ---------------------------------------------------------------- 백그라운드 작업

class Signals(QObject):
    done = Signal(object)
    failed = Signal(str)
    progress = Signal(object)


class Job(QRunnable):
    """fn(progress) 를 백그라운드에서 실행. 모든 신호는 (tag, 값) 으로 보낸다.
    tag 로 '어느 요청의 결과인지' 구분 (다른 교재를 이미 열었으면 늦게 온 결과는 버림).
    받는 쪽은 반드시 창(QObject)의 메서드로 연결 → 화면 갱신이 UI 스레드에서 실행됨."""

    def __init__(self, fn, tag=None):
        super().__init__()
        self.fn, self.tag = fn, tag
        self.sig = Signals()

    def run(self):
        tag = self.tag
        try:
            self.sig.done.emit((tag, self.fn(lambda m: self.sig.progress.emit((tag, m)))))
        except (R.RegistryError, UserError) as ex:
            self.sig.failed.emit((tag, str(ex)))
        except PermissionError as ex:
            self.sig.failed.emit((tag, f"파일에 쓸 수 없어요. 같은 이름의 파일이 열려 있으면 닫고 다시 시도해 주세요.\n({ex.filename})"))
        except Exception:                                   # 예상 못 한 오류도 창에 보여 준다
            self.sig.failed.emit((tag, "알 수 없는 오류가 발생했어요.\n\n" + traceback.format_exc(limit=3)))


def pix_to_qimage(pix):
    if pix.alpha:
        pix = fitz.Pixmap(pix, 0)
    img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format_RGB888)
    return img.copy()                                        # samples 메모리와 분리


# ---------------------------------------------------------------- 작업 함수 (UI 와 무관)

def scan_books(root):
    """교재 목록: [(상대경로, 상태)] — 크기·시각만 보고 빠르게.
    관리자가 '제외'한 파일(정답지·교사용 등)도 목록에는 '준비 중'으로 보여 준다 (열 수는 없음)."""
    disk = R.walk_pdfs(root)
    try:
        reg = R.load(root)
        warn = None
    except R.RegistryError as ex:
        reg, warn = R.empty_registry(), str(ex)
    out = []
    for rel, (size, mtime) in sorted(disk.items()):
        st = R.book_state(root, rel, size, mtime, reg)
        out.append((rel, R.PREPARING if st == R.HIDDEN else st))
    return out, warn


def open_book(root, rel, _progress):
    """해시 확인 → 좌표(+단원) 읽기. 썸네일은 단원을 고를 때 그 단원 것만 만든다(큰 교재도 바로 열림)."""
    reg = R.load(root)
    return books.load_coords(R.verify(root, rel, reg))


def render_thumbs(root, rel, problems, progress):
    """문제 썸네일을 하나씩 progress((id, QImage)) 로 보낸다."""
    with fitz.open(R.file_path(root, rel)) as doc:
        for p in problems:
            page = ready_page(doc, p["pdf_page"], p.get("clean"))
            pix = page.get_pixmap(dpi=THUMB_DPI, clip=fitz.Rect(*p["bbox"]))
            progress((p["id"], pix_to_qimage(pix)))


def parse_numbers(text, problems):
    """'12-20, 35, 3:5' → 문제 목록 (selector 문법, 쉼표·공백 구분). 반환 (문제들, 오류 문구들)"""
    tokens = [t for t in text.replace(",", " ").split() if t]
    return selector.resolve(tokens, problems)


def unique_path(folder, name, ext):
    p = os.path.join(folder, f"{name}.{ext}")
    n = 2
    while os.path.exists(p):
        p = os.path.join(folder, f"{name} ({n}).{ext}")
        n += 1
    return p


class UserError(Exception):
    """선생님에게 그대로 보여 줄 안내 문구."""


def crop_picks(root, picks, progress):
    """picks: [(교재 상대경로, 문제 dict)] 순서대로. 교재마다 해시를 다시 확인하고 자른다 → 빌더용 items."""
    reg = R.load(root)
    docs, items = {}, []
    try:
        for i, (rel, p) in enumerate(picks):
            if rel not in docs:
                progress(f"교재 확인 중… {os.path.basename(rel)}")
                R.verify(root, rel, reg)                     # 자르기 직전에 한 번 더 (바뀌었으면 중단)
                docs[rel] = fitz.open(R.file_path(root, rel))
            progress(f"문제 자르는 중… ({i + 1}/{len(picks)})")
            items.append(selector.crop_item(docs[rel], p))
        return items
    finally:
        for d in docs.values():
            d.close()


def make_files(root, picks, out_dir, name, formats, progress, cols="auto"):
    """새 파일 만들기. 반환: 만든 파일 경로들"""
    items = crop_picks(root, picks, progress)
    n_cols = selector.auto_cols(items) if cols == "auto" else int(cols)
    paths = []
    for ext, label, mod in FORMATS:
        if ext in formats:
            progress(f"{label} 만드는 중…")
            path = unique_path(out_dir, name, ext)
            mod.build(items, path, n_cols)
            paths.append(path)
    return paths


def backup_path(path):
    stem, ext = os.path.splitext(path)
    return f"{stem} (이어쓰기 전){ext}"


def append_file(root, picks, path, progress, cols="auto"):
    """이미 만든 파일(docx·pdf·hwpx 중 하나) 끝에 새 쪽부터 이어 붙여 같은 파일에 저장.
    이어 붙이기 직전 상태는 '이름 (이어쓰기 전).확장자' 로 남긴다 (매번 최신 직전 상태로 바뀜)."""
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mod = next((m for e, _, m in FORMATS if e == ext), None)
    if mod is None:
        raise UserError("Word(.docx), PDF(.pdf), 한글(.hwpx) 파일만 이어서 만들 수 있어요.")
    if not os.path.exists(path):
        raise UserError(f"파일을 찾을 수 없어요.\n{path}")
    with open(path, "r+b"):                               # 다른 프로그램에서 열려 있으면 여기서 PermissionError
        pass
    items = crop_picks(root, picks, progress)
    n_cols = selector.auto_cols(items) if cols == "auto" else int(cols)
    progress("원래 파일 백업 중…")
    shutil.copy2(path, backup_path(path))
    progress("이어 붙이는 중…")
    try:
        mod.append(items, path, n_cols)
    except PermissionError:
        raise
    except Exception:
        raise UserError("이 파일에는 이어 붙일 수 없어요. 파일이 손상됐거나 다른 형식일 수 있어요.\n"
                        "새로 만들기로 따로 만들어 주세요.\n\n" + traceback.format_exc(limit=2))
    return path


# ---------------------------------------------------------------- 화면

class MainWindow(QMainWindow):
    def __init__(self, root=None):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 860)
        LOG("창: 설정 읽는 중")
        self.pool = QThreadPool.globalInstance()
        self.cfg = load_config()
        self.root = root or self.cfg.get("root")
        self.book_rel = None                  # 지금 열린 교재
        self.problems = {}                    # id -> 문제 dict (열린 교재)
        self.groups = []                      # 단원(또는 10쪽 묶음) 목록 — books.unit_groups
        self.group_idx = None                 # 지금 보고 있는 단원
        self.grid_items = {}                  # id -> 가운데 칸 항목 (지금 단원)
        self.thumb_token = 0
        self.thumbs = {}                      # (rel, id) -> QPixmap (담은 목록에도 씀)
        self.picks = []                       # [(rel, id)] 담은 순서
        self.picked_data = {}                 # (rel, id) -> 문제 dict
        self.open_token = 0
        self.busy = False
        LOG("창: 화면 구성 중")
        self._build_ui()
        LOG("창: 화면 구성 완료")

    # -------- UI 구성
    def _build_ui(self):
        split = QSplitter()
        LOG("창: 왼쪽(교재 목록)")
        split.addWidget(self._left_panel())
        LOG("창: 가운데(문제)")
        split.addWidget(self._center_panel())
        LOG("창: 오른쪽(담은 문제)")
        split.addWidget(self._right_panel())
        split.setSizes([270, 820, 310])
        self.setCentralWidget(split)
        self.status = self.statusBar()

    def _left_panel(self):
        w = QWidget(); v = QVBoxLayout(w)
        title = QLabel("교재"); title.setFont(QFont("Malgun Gothic", 12, QFont.Bold))
        v.addWidget(title)
        row = QHBoxLayout()
        self.root_label = QLabel(); self.root_label.setStyleSheet("color:#666")
        self.root_label.setWordWrap(True)
        btn = QPushButton("폴더 변경"); btn.clicked.connect(self.choose_root)
        row.addWidget(self.root_label, 1); row.addWidget(btn)
        v.addLayout(row)
        row = QHBoxLayout()
        self.only_ready = QCheckBox("사용 가능한 교재만 보기")
        self.only_ready.setChecked(bool(self.cfg.get("only_ready", False)))
        self.only_ready.toggled.connect(self.fill_tree)
        refresh = QPushButton("새로고침"); refresh.clicked.connect(self.reload_books)
        row.addWidget(self.only_ready, 1); row.addWidget(refresh)
        v.addLayout(row)
        self.search = QLineEdit(); self.search.setPlaceholderText("교재 이름 검색")
        self.search.textChanged.connect(self.fill_tree)
        v.addWidget(self.search)
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True)
        self.tree.itemClicked.connect(self.on_tree_click)
        v.addWidget(self.tree, 1)
        legend = QLabel("✅ 사용 가능    ⏳ 준비 중 (관리자 등록 전)")
        legend.setStyleSheet("color:#666")
        v.addWidget(legend)
        return w

    def _center_panel(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.book_title = QLabel("왼쪽에서 교재를 고르세요")
        self.book_title.setFont(QFont("Malgun Gothic", 12, QFont.Bold))
        v.addWidget(self.book_title)
        hint = QLabel("단원을 고르고, 문제를 클릭하면 담기고 다시 클릭하면 빠집니다. 담은 순서대로 문서에 들어가요.")
        hint.setStyleSheet("color:#666")
        v.addWidget(hint)
        row = QHBoxLayout()
        self.pick_all_btn = QPushButton("이 단원 전체 담기"); self.pick_all_btn.clicked.connect(self.pick_all)
        self.pick_all_btn.setEnabled(False)
        row.addWidget(self.pick_all_btn)
        row.addSpacing(16)
        row.addWidget(QLabel("번호로 담기"))
        self.num_edit = QLineEdit(); self.num_edit.setPlaceholderText("예: 12-20, 35   (이 단원 안에서)")
        self.num_edit.returnPressed.connect(self.pick_by_numbers)
        self.num_btn = QPushButton("담기"); self.num_btn.clicked.connect(self.pick_by_numbers)
        self.num_edit.setEnabled(False); self.num_btn.setEnabled(False)
        row.addWidget(self.num_edit, 1); row.addWidget(self.num_btn)
        v.addLayout(row)

        inner = QSplitter()
        self.unit_tree = QTreeWidget(); self.unit_tree.setHeaderHidden(True)
        self.unit_tree.itemClicked.connect(self.on_unit_click)
        inner.addWidget(self.unit_tree)
        self.grid = QListWidget()
        self.grid.setViewMode(QListWidget.IconMode)
        self.grid.setResizeMode(QListWidget.Adjust)
        self.grid.setMovement(QListWidget.Static)
        self.grid.setIconSize(QSize(220, 180))
        self.grid.setGridSize(QSize(234, 222))
        self.grid.setSpacing(6)
        self.grid.setWordWrap(True)
        self.grid.setSelectionMode(QAbstractItemView.NoSelection)
        self.grid.itemClicked.connect(self.on_problem_click)
        inner.addWidget(self.grid)
        inner.setSizes([170, 650])
        v.addWidget(inner, 1)
        return w

    def _right_panel(self):
        w = QWidget(); v = QVBoxLayout(w)
        self.basket_title = QLabel("담은 문제 (0)")
        self.basket_title.setFont(QFont("Malgun Gothic", 12, QFont.Bold))
        v.addWidget(self.basket_title)
        tip = QLabel("끌어서 순서를 바꿀 수 있어요."); tip.setStyleSheet("color:#666")
        v.addWidget(tip)
        self.basket = QListWidget()
        self.basket.setIconSize(QSize(90, 60))
        self.basket.setDragDropMode(QAbstractItemView.InternalMove)
        self.basket.model().rowsMoved.connect(self.on_basket_reordered)
        v.addWidget(self.basket, 1)
        row = QHBoxLayout()
        rm = QPushButton("선택 빼기"); rm.clicked.connect(self.remove_selected)
        clr = QPushButton("모두 비우기"); clr.clicked.connect(self.clear_picks)
        row.addWidget(rm); row.addWidget(clr)
        v.addLayout(row)

        line = QFrame(); line.setFrameShape(QFrame.HLine); v.addWidget(line)
        v.addWidget(QLabel("파일 이름"))
        self.name_edit = QLineEdit(time.strftime("학습지_%m%d"))
        v.addWidget(self.name_edit)
        v.addWidget(QLabel("형식"))
        self.fmt_boxes = {}
        saved = self.cfg.get("formats", ["docx", "pdf"])
        for ext, label, _ in FORMATS:
            cb = QCheckBox(label); cb.setChecked(ext in saved)
            self.fmt_boxes[ext] = cb; v.addWidget(cb)
        v.addWidget(QLabel("단"))
        row = QHBoxLayout()
        self.cols_boxes = {}
        saved_cols = self.cfg.get("cols", "2")                 # 기본은 2단 (학원 양식)
        for key, label in (("2", "2단 (쪽당 4문제)"), ("1", "1단 (쪽당 2문제)"), ("auto", "자동")):
            rb = QRadioButton(label); rb.setChecked(key == saved_cols)
            self.cols_boxes[key] = rb; row.addWidget(rb)
        v.addLayout(row)
        tip = QLabel("쪽 폭 전체를 쓰는 넓은 문제(마플교과서 등)는 1단이나 자동을 고르면 크게 들어가요.")
        tip.setStyleSheet("color:#666"); tip.setWordWrap(True)
        v.addWidget(tip)
        v.addWidget(QLabel("저장 위치"))
        row = QHBoxLayout()
        self.out_dir = self.cfg.get("out_dir") if os.path.isdir(self.cfg.get("out_dir", "")) else desktop_dir()
        self.out_label = QLabel(self.out_dir); self.out_label.setWordWrap(True)
        self.out_label.setStyleSheet("color:#444")
        b = QPushButton("변경"); b.clicked.connect(self.choose_out_dir)
        row.addWidget(self.out_label, 1); row.addWidget(b)
        v.addLayout(row)
        self.make_btn = QPushButton("만들기")
        self.make_btn.setMinimumHeight(44)
        self.make_btn.setStyleSheet("font-size:15px; font-weight:bold;")
        self.make_btn.clicked.connect(self.make)
        v.addWidget(self.make_btn)
        self.append_btn = QPushButton("기존 파일에 이어서 만들기…")
        self.append_btn.setToolTip("전에 만든 학습지(docx·pdf·hwpx)를 골라, 마지막 쪽 다음 쪽부터 담은 문제를 이어 붙여요.\n"
                                   "원래 파일은 '이름 (이어쓰기 전)'으로 백업해 둬요.")
        self.append_btn.clicked.connect(self.append_to_file)
        v.addWidget(self.append_btn)
        return w

    # -------- 교재 폴더
    def start(self):
        if not self.root:
            self.root = DEFAULT_ROOT if os.path.isdir(DEFAULT_ROOT) else None
        if not self.root or not os.path.isdir(self.root):
            QMessageBox.information(self, APP_NAME, "교재 폴더를 찾을 수 없어요.\nMYBOX의 교재 폴더(예: N:\\개인\\내문서)를 골라 주세요.")
            if not self.choose_root():
                return
        self.reload_books()

    def choose_root(self):
        d = QFileDialog.getExistingDirectory(self, "교재 폴더 선택", self.root or "")
        if not d:
            return False
        self.root = os.path.normpath(d)
        self.cfg["root"] = self.root; save_config(self.cfg)
        self.reload_books()
        return True

    def reload_books(self):
        self.root_label.setText(self.root or "")
        self.tree.clear()
        self.tree.addTopLevelItem(QTreeWidgetItem(["불러오는 중…"]))
        root = self.root
        job = Job(lambda _p: scan_books(root))
        job.sig.done.connect(self.on_books_loaded)
        job.sig.failed.connect(self.on_books_failed)
        self.pool.start(job)

    def on_books_loaded(self, payload):
        self.books, warn = payload[1]
        self.fill_tree()
        ready = sum(1 for _, s in self.books if s == R.READY)
        self.status.showMessage(f"교재 {len(self.books)}개 중 사용 가능 {ready}개")
        if warn:
            QMessageBox.warning(self, APP_NAME, warn)

    def on_books_failed(self, payload):
        msg = payload[1]
        self.books = []
        self.tree.clear()
        QMessageBox.warning(self, APP_NAME, msg)

    def fill_tree(self):
        self.cfg["only_ready"] = self.only_ready.isChecked(); save_config(self.cfg)
        books_ = getattr(self, "books", [])
        q = self.search.text().strip().lower()
        shown = [(rel, st) for rel, st in books_
                 if (st == R.READY or not self.only_ready.isChecked())
                 and (not q or q in rel.lower())]
        self.tree.clear()
        folders = {}

        def folder_item(parts):
            key = "/".join(parts)
            if key in folders:
                return folders[key]
            parent = folder_item(parts[:-1]) if len(parts) > 1 else None
            it = QTreeWidgetItem(["📁 " + parts[-1]])
            (parent.addChild(it) if parent else self.tree.addTopLevelItem(it))
            folders[key] = it
            return it

        for rel, st in shown:
            parts = rel.split("/")
            name = parts[-1][:-4] if parts[-1].lower().endswith(".pdf") else parts[-1]
            it = QTreeWidgetItem([("✅ " if st == R.READY else "⏳ ") + name])
            it.setData(0, ROLE_REL, rel)
            it.setData(0, ROLE_PID, st)
            if st != R.READY:
                it.setForeground(0, QBrush(GRAY))
                it.setToolTip(0, "준비 중인 교재예요. 관리자에게 등록을 요청해 주세요.")
            (folder_item(parts[:-1]).addChild(it) if len(parts) > 1 else self.tree.addTopLevelItem(it))
        if self.only_ready.isChecked() or q:
            self.tree.expandAll()
        if not shown:
            self.tree.addTopLevelItem(QTreeWidgetItem(["(표시할 교재가 없어요)"]))

    # -------- 교재 열기 / 문제 고르기
    def on_tree_click(self, item):
        rel = item.data(0, ROLE_REL)
        if not rel:
            return
        if item.data(0, ROLE_PID) != R.READY:
            self.status.showMessage("준비 중인 교재예요. 관리자에게 등록을 요청해 주세요.", 5000)
            return
        self.open(rel)

    def open(self, rel):
        self.open_token += 1
        token = self.open_token
        self.book_rel = rel
        self.problems, self.groups, self.group_idx, self.grid_items = {}, [], None, {}
        self.grid.clear()
        self.unit_tree.clear()
        self._set_book_controls(False)
        self.book_title.setText(os.path.basename(rel)[:-4] + "  — 여는 중… (교재 확인)")
        root = self.root
        job = Job(lambda progress: open_book(root, rel, progress), tag=(token, rel))
        job.sig.done.connect(self.on_book_opened)
        job.sig.failed.connect(self.on_book_failed)
        self.pool.start(job)

    def _set_book_controls(self, on):
        for w in (self.pick_all_btn, self.num_edit, self.num_btn):
            w.setEnabled(on)

    def on_book_opened(self, payload):
        (token, _rel), coords = payload
        if token != self.open_token:
            return                                            # 다른 교재를 이미 열었음
        self.problems = {p["id"]: p for p in coords["problems"]}
        self.groups = books.unit_groups(coords)
        has_units = bool(coords.get("units"))
        self.book_title.setText(f"{os.path.basename(self.book_rel)[:-4]}  — 문제 {len(self.problems)}개"
                                + (f", 단원 {len(self.groups)}개" if has_units else ""))
        self.fill_units()
        self._set_book_controls(True)
        if self.groups:
            self.show_group(0)

    def on_book_failed(self, payload):
        (token, _rel), msg = payload
        if token != self.open_token:
            return
        self.book_title.setText("교재를 열지 못했어요")
        QMessageBox.warning(self, APP_NAME, msg)

    # -------- 단원
    def fill_units(self):
        self.unit_tree.clear()
        parents = {}
        for i, g in enumerate(self.groups):
            it = QTreeWidgetItem([self._unit_label(g)])
            it.setData(0, ROLE_REL, i)
            grp = g.get("group")
            if grp:
                if grp not in parents:
                    parents[grp] = QTreeWidgetItem([grp])
                    parents[grp].setFlags(Qt.ItemIsEnabled)
                    self.unit_tree.addTopLevelItem(parents[grp])
                parents[grp].addChild(it)
            else:
                self.unit_tree.addTopLevelItem(it)
        self.unit_tree.expandAll()

    def _unit_label(self, g):
        n = sum(1 for p in g["problems"] if (self.book_rel, p["id"]) in self.picks)
        return f"{g['title']}  ({len(g['problems'])})" + (f"  ✔{n}" if n else "")

    def _unit_items(self):
        out, stack = [], [self.unit_tree.topLevelItem(i) for i in range(self.unit_tree.topLevelItemCount())]
        while stack:
            it = stack.pop(0)
            if it.data(0, ROLE_REL) is not None:
                out.append(it)
            stack[0:0] = [it.child(i) for i in range(it.childCount())]
        return out

    def on_unit_click(self, item):
        idx = item.data(0, ROLE_REL)
        if idx is not None:
            self.show_group(idx)

    def show_group(self, idx):
        """단원 하나의 문제만 가운데에 보여 주고, 아직 없는 썸네일만 만든다."""
        self.group_idx = idx
        for it in self._unit_items():
            if it.data(0, ROLE_REL) == idx:
                self.unit_tree.setCurrentItem(it)
        g = self.groups[idx]
        self.grid.clear()
        self.grid_items = {}
        todo = []
        for p in g["problems"]:
            it = QListWidgetItem()
            it.setData(ROLE_PID, p["id"])
            it.setTextAlignment(Qt.AlignHCenter | Qt.AlignTop)
            key = (self.book_rel, p["id"])
            if key in self.thumbs:
                it.setIcon(QIcon(self.thumbs[key]))
            else:
                todo.append(p)
            self.grid.addItem(it)
            self.grid_items[p["id"]] = it
            self._paint_grid_item(it)
        self.grid.scrollToTop()
        if todo:
            self.thumb_token += 1
            root, rel = self.root, self.book_rel
            job = Job(lambda progress: render_thumbs(root, rel, todo, progress),
                      tag=(self.open_token, self.thumb_token, rel))
            job.sig.progress.connect(self.on_thumb)
            job.sig.failed.connect(self.on_thumb_failed)
            self.pool.start(job)

    def on_thumb(self, payload):
        (token, _tt, rel), (pid, qimg) = payload
        pm = QPixmap.fromImage(qimg)
        self.thumbs[(rel, pid)] = pm                          # 다른 단원으로 옮겨 가도 캐시는 남김
        if token == self.open_token and pid in self.grid_items:
            self.grid_items[pid].setIcon(QIcon(pm))

    def on_thumb_failed(self, payload):
        (token, _tt, _rel), msg = payload
        if token == self.open_token:
            self.status.showMessage("미리보기를 만들지 못했어요: " + msg.splitlines()[0], 8000)

    def pick_by_numbers(self):
        if self.group_idx is None:
            return
        text = self.num_edit.text().strip()
        if not text:
            return
        chosen, errors = parse_numbers(text, self.groups[self.group_idx]["problems"])
        for p in chosen:
            key = (self.book_rel, p["id"])
            if key not in self.picks:
                self.picks.append(key)
                self.picked_data[key] = p
        self.refresh_picks()
        if errors:
            QMessageBox.information(self, APP_NAME, f"{len(chosen)}문제를 담았어요.\n\n담지 못한 것:\n  "
                                    + "\n  ".join(errors))
        else:
            self.num_edit.clear()
            self.status.showMessage(f"{len(chosen)}문제를 담았어요.", 4000)

    def _paint_grid_item(self, it):
        # 글귀는 담기 전후 모두 2줄로 고정한다. 줄 수가 바뀌면 칸 높이가 줄어들면서
        # 예전 글귀 자리가 다시 그려지지 않아 잔상(파란 배경 글귀)이 남는다.
        key = (self.book_rel, it.data(ROLE_PID))
        p = self.problems[key[1]]
        label = f"{p['page']}쪽  {selector.num_text(p)}번"
        if key in self.picks:
            n = self.picks.index(key) + 1
            it.setText(f"{label}\n✔ {n}번째 담김")
            it.setBackground(QBrush(PICKED_BG))
        else:
            it.setText(f"{label}\n ")
            it.setData(Qt.BackgroundRole, None)           # 배경 지정 자체를 없앰

    def on_problem_click(self, it):
        key = (self.book_rel, it.data(ROLE_PID))
        if key in self.picks:
            self.picks.remove(key)
        else:
            self.picks.append(key)
            self.picked_data[key] = self.problems[key[1]]
        self.refresh_picks()

    def pick_all(self):
        """이 단원 전체 담기 (가운데에 보이는 문제 전부)"""
        for i in range(self.grid.count()):
            key = (self.book_rel, self.grid.item(i).data(ROLE_PID))
            if key not in self.picks:
                self.picks.append(key)
                self.picked_data[key] = self.problems[key[1]]
        self.refresh_picks()

    def refresh_picks(self):
        for i in range(self.grid.count()):
            self._paint_grid_item(self.grid.item(i))
        self.grid.viewport().update()                      # 칸 전체 다시 그리기 (잔상 방지)
        for it in self._unit_items():                      # 단원 옆 '✔담은 수'
            it.setText(0, self._unit_label(self.groups[it.data(0, ROLE_REL)]))
        self.basket.blockSignals(True)
        self.basket.clear()
        for n, key in enumerate(self.picks, 1):
            rel, pid = key
            p = self.picked_data[key]
            book = os.path.basename(rel)[:-4]
            it = QListWidgetItem(f"{n}.  {p['page']}쪽 {selector.num_text(p)}번\n     {book}")
            it.setData(ROLE_REL, rel); it.setData(ROLE_PID, pid)
            if key in self.thumbs:
                it.setIcon(QIcon(self.thumbs[key]))
            self.basket.addItem(it)
        self.basket.blockSignals(False)
        pages = -(-len(self.picks) // 4) if self.picks else 0
        self.basket_title.setText(f"담은 문제 ({len(self.picks)})  · 약 {pages}쪽")

    def on_basket_reordered(self, *_):
        self.picks = [(self.basket.item(i).data(ROLE_REL), self.basket.item(i).data(ROLE_PID))
                      for i in range(self.basket.count())]
        self.refresh_picks()

    def remove_selected(self):
        for it in self.basket.selectedItems():
            key = (it.data(ROLE_REL), it.data(ROLE_PID))
            if key in self.picks:
                self.picks.remove(key)
        self.refresh_picks()

    def clear_picks(self):
        self.picks = []
        self.refresh_picks()

    # -------- 저장
    def choose_out_dir(self):
        d = QFileDialog.getExistingDirectory(self, "저장 위치 선택", self.out_dir)
        if d:
            self.out_dir = os.path.normpath(d)
            self.out_label.setText(self.out_dir)
            self.cfg["out_dir"] = self.out_dir; save_config(self.cfg)

    def make(self):
        if self.busy:
            return
        if not self.picks:
            QMessageBox.information(self, APP_NAME, "담은 문제가 없어요. 가운데에서 문제를 클릭해 담아 주세요.")
            return
        formats = [ext for ext, cb in self.fmt_boxes.items() if cb.isChecked()]
        cols = next(k for k, rb in self.cols_boxes.items() if rb.isChecked())
        if not formats:
            QMessageBox.information(self, APP_NAME, "만들 형식을 하나 이상 골라 주세요.")
            return
        name = self.name_edit.text().strip()
        bad = set('\\/:*?"<>|')
        if not name or any(c in bad for c in name):
            QMessageBox.information(self, APP_NAME, '파일 이름을 확인해 주세요. (\\ / : * ? " < > | 는 쓸 수 없어요)')
            return
        self.cfg["formats"] = formats; save_config(self.cfg)
        picks = [(rel, self.picked_data[(rel, pid)]) for rel, pid in self.picks]
        root, out_dir = self.root, self.out_dir
        self.busy = True
        self.make_btn.setEnabled(False); self.make_btn.setText("만드는 중…")
        self.cfg["cols"] = cols; save_config(self.cfg)
        job = Job(lambda progress: make_files(root, picks, out_dir, name, formats, progress, cols))
        job.sig.progress.connect(self.on_make_progress)
        job.sig.done.connect(self.on_made)
        job.sig.failed.connect(self.on_make_failed)
        self.pool.start(job)

    def append_to_file(self):
        if self.busy:
            return
        if not self.picks:
            QMessageBox.information(self, APP_NAME, "담은 문제가 없어요. 가운데에서 문제를 클릭해 담아 주세요.")
            return
        path, _ = QFileDialog.getOpenFileName(self, "이어서 만들 학습지 고르기", self.out_dir,
                                              "학습지 (*.docx *.pdf *.hwpx)")
        if not path:
            return
        path = os.path.normpath(path)
        cols = next(k for k, rb in self.cols_boxes.items() if rb.isChecked())
        picks = [(rel, self.picked_data[(rel, pid)]) for rel, pid in self.picks]
        root = self.root
        self.busy = True
        self.make_btn.setEnabled(False); self.append_btn.setEnabled(False)
        self.append_btn.setText("이어 붙이는 중…")
        job = Job(lambda progress: append_file(root, picks, path, progress, cols))
        job.sig.progress.connect(self.on_make_progress)
        job.sig.done.connect(self.on_appended)
        job.sig.failed.connect(self.on_make_failed)
        self.pool.start(job)

    def on_appended(self, payload):
        path = payload[1]
        self._make_finished()
        self.status.showMessage("완료", 5000)
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setText(f"이어서 만들었어요. ({len(self.picks)}문제)\n\n  • {os.path.basename(path)}\n\n"
                    f"이어 붙이기 전 파일은 '{os.path.basename(backup_path(path))}'로 남겨 뒀어요.")
        open_btn = box.addButton("파일 열기", QMessageBox.AcceptRole)
        box.addButton("닫기", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    def _make_finished(self):
        self.busy = False
        self.make_btn.setEnabled(True); self.make_btn.setText("만들기")
        self.append_btn.setEnabled(True); self.append_btn.setText("기존 파일에 이어서 만들기…")

    def on_make_progress(self, payload):
        self.status.showMessage(payload[1])

    def on_made(self, payload):
        paths = payload[1]
        self._make_finished()
        self.status.showMessage("완료", 5000)
        names = "\n".join("  • " + os.path.basename(p) for p in paths)
        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setText(f"만들었어요. ({len(self.picks)}문제)\n\n{names}\n\n저장 위치: {self.out_dir}")
        open_btn = box.addButton("폴더 열기", QMessageBox.AcceptRole)
        box.addButton("닫기", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(self.out_dir))

    def on_make_failed(self, payload):
        msg = payload[1]
        self._make_finished()
        self.status.clearMessage()
        QMessageBox.warning(self, APP_NAME, msg)


def selftest(root, out_dir):
    """exe 포장 점검용 (화면 없이): 첫 사용 가능 교재에서 3문제를 세 형식으로 만들어 결과를 selftest.txt 에 남김."""
    os.makedirs(out_dir, exist_ok=True)
    log = []
    try:
        books_, warn = scan_books(root)
        ready = [rel for rel, st in books_ if st == R.READY]
        log.append(f"교재 {len(books_)}개, 사용 가능 {len(ready)}개, 경고 {warn}")
        rel = ready[0]
        thumbs = []
        coords = open_book(root, rel, None)
        groups = books.unit_groups(coords)
        render_thumbs(root, rel, groups[0]["problems"], thumbs.append)
        log.append("단원: " + ", ".join(f"{g['title']}({len(g['problems'])})" for g in groups))
        picks = [(rel, p) for p in coords["problems"][:3]]
        paths = make_files(root, picks, out_dir, "selftest", ["docx", "pdf", "hwpx"], lambda m: None)
        log.append(f"썸네일 {len(thumbs)}개, 만든 파일: " + ", ".join(os.path.basename(p) for p in paths))
        log.append("OK")
    except Exception:
        log.append("FAIL\n" + traceback.format_exc())
    with open(os.path.join(out_dir, "selftest.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log))


class NoAccessibilityFilter(QAbstractNativeEventFilter):
    """접근성(UI Automation) 요청 WM_GETOBJECT 를 Qt 가 처리하기 전에 무시한다.
    일부 Windows 11(24H2 이후) PC 에서 이 요청 처리 중 창 만들기가 강제 종료되는 문제 우회용."""

    def __init__(self, log):
        super().__init__()
        self.log = log
        self.count = 0

    def nativeEventFilter(self, event_type, message):
        try:
            import ctypes
            from ctypes import wintypes
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == 0x003D:                       # WM_GETOBJECT
                self.count += 1
                if self.count <= 5:
                    self.log(f"접근성 요청(WM_GETOBJECT) 무시 #{self.count} lp=0x{msg.lParam & 0xFFFFFFFF:x}")
                return True, 0
        except Exception as ex:
            self.log(f"접근성 필터 오류: {ex}")
        return False, 0


def diag_probe(app, probe, log):
    """진단용 최소 창: bare(빈 창) / frameless(제목 표시줄 없음) / qwindow(위젯 없는 Qt 창) /
    lineedit(입력칸) / lists(목록·트리) / labels(글자)."""
    if "--diag-msghook" in sys.argv:
        from core import diagtools
        diagtools.install_msg_hook(log)
    if probe == "qwindow":
        win = QWindow()
        win.resize(300, 200)
        log("진단 창(qwindow): 숨긴 채 Windows 창 만드는 중")
        win.create()
        log("진단 창(qwindow): 만들어짐 → 보이는 중")
        win.show()
        log("진단 창(qwindow) 표시됨")
        QTimer.singleShot(1500, app.quit)
        return app.exec()
    w = QWidget(None, Qt.FramelessWindowHint) if probe == "frameless" else QWidget()
    w.setWindowTitle(f"진단 {probe}")
    lay = QVBoxLayout(w)
    if probe == "lineedit":
        lay.addWidget(QLineEdit("입력칸"))
    elif probe == "lists":
        t = QTreeWidget(); t.addTopLevelItem(QTreeWidgetItem(["항목"])); lay.addWidget(t)
        g = QListWidget(); g.setViewMode(QListWidget.IconMode); g.addItem("문제"); lay.addWidget(g)
    elif probe == "labels":
        lay.addWidget(QLabel("글자 표시 시험")); lay.addWidget(QPushButton("버튼")); lay.addWidget(QCheckBox("체크"))
    w.resize(300, 200)
    try:
        from core import diagtools
        mods = diagtools.foreign_modules()
        log(f"끼어든 DLL {len(mods)}개 (Microsoft·앱 것 제외): " + (" | ".join(mods) if mods else "없음"))
    except Exception as ex:
        log(f"DLL 목록 확인 실패: {ex}")
    log(f"진단 창({probe}): 숨긴 채 Windows 창 만드는 중")
    w.winId()
    log(f"진단 창({probe}): 만들어짐 → 보이는 중")
    w.show()
    log(f"진단 창({probe}) 표시됨")
    QTimer.singleShot(1500, app.quit)
    return app.exec()


def main(log=None, on_shown=None):
    global LOG
    log = log or (lambda m: None)
    LOG = log
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", help="교재 폴더 (지정하지 않으면 저장된 설정 / N:\\개인\\내문서)")
    ap.add_argument("--selftest", metavar="OUT_DIR", help=argparse.SUPPRESS)
    args, _ = ap.parse_known_args()
    if args.selftest:
        selftest(args.root, args.selftest)
        return
    def qt_message(mode, context, message):              # Qt 내부 경고·치명 오류도 실행 기록에 남김
        log(f"[Qt {mode.name if hasattr(mode, 'name') else mode}] {message}")
    if "--diag-plain" not in sys.argv:                     # 진단: 기록 장치 없이도 시험
        qInstallMessageHandler(qt_message)
    log(f"Qt 설정: QT_QPA_PLATFORM={os.environ.get('QT_QPA_PLATFORM', '-')} "
        f"QT_OPENGL={os.environ.get('QT_OPENGL', '-')}")
    app = QApplication(sys.argv)
    log(f"Qt 시작됨 (Qt {qVersion()}, 기본 스타일 {app.style().name()})")
    if "--diag-nogpuguard" not in sys.argv:                # 일부 그래픽 드라이버에서 창 만들 때 죽는 문제 우회
        try:
            from core import gpu_guard
            gpu_guard.block_d3d9(log)
        except Exception as ex:
            log(f"그래픽 우회 실패: {ex}")
    if "--diag-noaccess" in sys.argv:                      # 진단: 접근성 요청 무시
        app._no_access = NoAccessibilityFilter(log)
        app.installNativeEventFilter(app._no_access)
        log("접근성 요청 무시 필터 설치됨")
    probe = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--diag-probe=")), None)
    if probe:                                              # 진단: 최소한의 창으로 어느 부품에서 죽는지 찾기
        sys.exit(diag_probe(app, probe, log))
    # Fusion: Qt 가 직접 그리는 스타일 — Windows 버전별 기본 스타일(windows11 등) 차이·충돌을 피함
    app.setStyle("Fusion")
    log("스타일 Fusion 적용")
    app.setApplicationName(APP_NAME)
    app.setFont(QFont("Malgun Gothic", 10))
    win = MainWindow(root=args.root)
    if "--diag-msghook" in sys.argv:
        from core import diagtools
        diagtools.install_msg_hook(log)
    win.show()
    log(f"창 표시됨 (교재 폴더 설정: {win.root})")
    if on_shown:
        on_shown()
    win.start()
    if "--diag-autoclose" in sys.argv:                     # 진단: 창이 뜨는지만 보고 3초 뒤 닫음
        QTimer.singleShot(3000, app.quit)
    code = app.exec()
    log(f"창 닫힘 (코드 {code})")
    sys.exit(code)


if __name__ == "__main__":
    main()
