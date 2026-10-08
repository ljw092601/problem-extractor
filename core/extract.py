# -*- coding: utf-8 -*-
"""
교재 PDF → 문제 좌표 추출 (텍스트 PDF · 스캔본 공통). 관리자(등록 작업)용.

레이아웃 설정 (layout.json) — 교재마다 한 번 정한다. 좌표 단위는 pt (PDF 좌표, 왼쪽 위 0,0):
{
  "source": "ocr",                       # "text"(PDF 글자 정보) 또는 "ocr"(스캔본: Windows OCR)
  "pages": [[20, 180]],                  # 문제가 있는 쪽 범위(1부터, 양끝 포함). 여러 구간 가능. 생략 = 전체
  "skip_pages": [25, [49, 50]],          # (선택) 건너뛸 쪽 (묶음 연습문제 쪽 등)
  "manual_labels": [{"page": 22, "col": 1, "y": 288, "num": 113}],
                                         # (선택) OCR 이 끝내 못 읽은 번호를 직접: 쪽, 단(0=왼쪽,1=오른쪽), 번호 윗끝 y
  "label_regex": "^(\\d{4})$",           # 문제 번호 모양. 첫 괄호 = 번호. 예: "^(\\d{1,3})\\.?$" (1. / 01)
  "text_size": [12.5, 13.5],             # (text 전용) 번호 글자 크기 범위
  "label_min_h": 12,                     # (선택) 번호 글자 최소 높이(pt). 보기 '①12' 를 '012' 로 읽는 오인식 거르기
  "body": [45, 800],                     # 본문 세로 범위 (머리말·꼬리말 제외)
  "columns":      [{"x": [20, 285], "label_x": [22, 45]}, {"x": [288, 560], "label_x": [288, 310]}],
  "columns_even": [...],                 # (선택) 짝수 쪽이 좌우로 밀려 있으면 따로
  "top_pad": 6,                          # 번호 위로 더 포함할 높이 (번호 위 '빈출'·'서술형' 도장 등)
  "bot_pad": 6,                          # 내용 끝 아래 여백
  "gap_stop": 40,                        # 내용 뒤로 이만큼 비면 문제 끝으로 봄 (문제 안 여백이 크면 늘림)
  "ocr_dpi": [150, 200],                 # (ocr 전용) 이 해상도들로 읽어 합침 (놓침 방지)
  "group_regex": "...",                  # (선택) 묶음 머리글 모양. 기본: [0125~0128] / [01-03] 같은 '[번호~번호]'
  "group_gap_stop": 45,                  # (선택) 묶음 끝 판단 여백 (기본 = gap_stop). 소문제 사이가 넓어 잘리면 늘림
  "manual_groups": [{"page": 25, "col": 1, "y": 357, "range": [125, 128]}]
                                         # (선택) OCR 이 못 읽은 묶음 머리글을 직접
}
  - x: 그 단의 자르기 좌우 범위 (가운데 구분선을 물지 않게!)
  - label_x: 번호 '왼쪽 끝'이 들어오는 x 범위. 여기서 벗어난 숫자는 번호가 아님(보기 ①② 등 걸러짐)

묶음 문제: 단 왼쪽(label_x 근처)에서 시작하는 줄이 '[0125~0128] …' 모양이면 묶음 머리글로 본다.
  머리글부터 범위 안 소문제들 끝까지를 '문제 하나'로 자르고 num=0125, num_end=0128, label="0125~0128".
"""
import json
import os
import re

import fitz

from core.pdfpage import ready_page

TRIM_DPI = 100
GROUP_REGEX = r"^\s*[\[【]\s*(\d{1,4})\s*[~∼〜\-－—–]\s*(\d{1,4})"    # 대괄호 필수 (소단원 '02-4' 등과 구분)


# ---------------------------------------------------------------- 설정

def load_layout(path):
    with open(path, encoding="utf-8") as f:
        text = f.read()
    try:
        cfg = json.loads(text)
    except ValueError:
        # 셸을 거치며 "\\d" 가 "\d" 로 바뀐 경우 (JSON 에서 잘못된 이스케이프) 바로잡기
        cfg = json.loads(re.sub(r'(?<!\\)\\(?=[dDsSwWbB.()\[\]{}+*?^$|])', r"\\\\", text))
    cfg.setdefault("source", "text")
    cfg.setdefault("top_pad", 6)
    cfg.setdefault("bot_pad", 6)
    cfg.setdefault("gap_stop", 40)
    cfg.setdefault("ocr_dpi", [150, 200])
    return cfg


def page_list(cfg, page_count, only=None):
    """처리할 쪽 (0부터). only: 1부터 쪽 번호 목록(시험용)"""
    if only:
        return [p - 1 for p in only if 1 <= p <= page_count]
    ranges = cfg.get("pages") or [[1, page_count]]
    skip = set()
    for s in cfg.get("skip_pages", []):                   # 건너뛸 쪽: 숫자 또는 [a, b]
        skip.update(range(s[0], s[1] + 1) if isinstance(s, list) else [s])
    out = []
    for a, b in ranges:
        out.extend(p for p in range(max(1, a) - 1, min(b, page_count)) if p + 1 not in skip)
    return out


def drop_outliers(problems, window=30, look=5):
    """앞 번호에서 이어지지 않는 튀는 번호(연도·쪽 참조 등 잘못 읽은 숫자)를 뺀다.
    앞 번호 p 다음이 p < n <= p+window 가 아니고, 뒤쪽 몇 개 안에 p 를 잇는 번호가 있으면 가운데 것들은 버림.
    (뒤에 잇는 번호가 없으면 = 단원마다 번호가 새로 시작하는 경우 → 그대로 둠)"""
    out, dropped = [], []
    for i, p in enumerate(problems):
        prev = out[-1].get("num_end", out[-1]["num"]) if out else None
        if prev is None or prev < p["num"] <= prev + window:
            out.append(p)
            continue
        if any(prev < q["num"] <= prev + window for q in problems[i + 1:i + 1 + look]):
            dropped.append((p["page"], p["num"]))
            continue
        out.append(p)
    return out, dropped


def columns_for(cfg, pno):
    """pno: 0부터. 1부터 센 쪽이 짝수면 columns_even (있으면)"""
    if (pno + 1) % 2 == 0 and cfg.get("columns_even"):
        return cfg["columns_even"]
    return cfg["columns"]


# ---------------------------------------------------------------- 번호 찾기

def _text_tokens(page):
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                yield s["text"].strip(), s["bbox"], s["size"]


def _text_lines(page):
    out = []
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            t = "".join(s["text"] for s in l["spans"]).strip()
            if t:
                out.append((t, tuple(l["bbox"])))
    return out


def _ocr_page(page, cfg):
    """스캔본 한 쪽 OCR → (단어 조각들, 줄들). 여러 해상도 결과를 합친다."""
    from . import winocr
    body = cfg.get("body") or [0, page.rect.height]
    clip = fitz.Rect(0, body[0], page.rect.width, body[1])
    toks, lines = [], []
    for dpi in cfg["ocr_dpi"]:
        pix = page.get_pixmap(dpi=dpi, clip=clip, colorspace=fitz.csGRAY)
        sc = 72 / dpi

        def conv(a, b, c, d):
            return (a * sc, b * sc + body[0], c * sc, d * sc + body[0])
        for text, x0, y0, x1, y1, words in winocr.ocr_lines(pix):
            lb = conv(x0, y0, x1, y1)
            if not any(t == text and abs(b[0] - lb[0]) < 6 and abs(b[1] - lb[1]) < 6 for t, b in lines):
                lines.append((text, lb))
            for wt, a, b, c, d in words:
                bbox = conv(a, b, c, d)
                if any(t == wt and abs(bb[0] - bbox[0]) < 6 and abs(bb[1] - bbox[1]) < 6 for t, bb, _ in toks):
                    continue                               # 다른 해상도에서 이미 찾은 것
                toks.append((wt, bbox, bbox[3] - bbox[1]))
    return toks, lines


def _ocr_tokens(page, cfg):
    return _ocr_page(page, cfg)[0]


def page_content(page, cfg):
    """→ (글자 조각들 [(글자, bbox, 크기)], 줄들 [(글자, bbox)])"""
    if cfg["source"] == "ocr":
        return _ocr_page(page, cfg)
    return list(_text_tokens(page)), _text_lines(page)


def _match_labels(toks, cfg, cols, body, slack=0):
    """글자 조각 → 번호 후보. slack: 번호 영역(label_x)을 좌우로 넓혀 볼 여유(pt).
    반환: (번호 목록, 번호 영역 밖에서 번호 모양이 보인 개수 — 묶음문제 등 다른 배치의 신호)"""
    rx = re.compile(cfg["label_regex"])
    size_rng = cfg.get("text_size")
    out, offband = [], 0
    for text, bbox, size in toks:
        m = rx.match(text)
        if not m:
            continue
        if cfg["source"] == "text" and size_rng and not (size_rng[0] <= size <= size_rng[1]):
            continue
        if cfg.get("label_min_h") and bbox[3] - bbox[1] < cfg["label_min_h"]:
            continue                                      # (OCR) 보기 '①12' 를 '012' 로 읽은 작은 조각 등
        if not (body[0] <= bbox[1] <= body[1]):
            continue
        ci = next((i for i, c in enumerate(cols)
                   if c["label_x"][0] - slack <= bbox[0] <= c["label_x"][1] + slack), None)
        if ci is None:
            offband += 1
            continue
        out.append({"num": int(m.group(1)), "label": text, "col": ci,
                    "x": round(bbox[0], 1), "y0": round(bbox[1], 1), "y1": round(bbox[3], 1)})
    return out, offband


def _dedup(labels):
    """같은 단·거의 같은 높이에 둘 이상이면 하나만. 단 → 위에서 아래 순."""
    labels.sort(key=lambda d: (d["col"], d["y0"]))
    out = []
    for d in labels:
        if out and out[-1]["col"] == d["col"] and abs(out[-1]["y0"] - d["y0"]) < 8:
            continue
        out.append(d)
    return out


def _has_gap(labels, prev_last=None, covered=()):
    nums = sorted(set(([prev_last] if prev_last is not None else []) + [d["num"] for d in labels])
                  | set(covered))
    return any(1 < b - a <= 30 for a, b in zip(nums, nums[1:]))


def _rescue_tokens(page, cfg, cols, body):
    """번호 영역만 좁게 잘라 높은 해상도로 다시 읽기 (옆의 '서술형' 뱃지 등에 섞여 놓친 번호 찾기)."""
    from . import winocr
    toks = []
    for c in cols:
        x0, x1 = c["label_x"][0] - 4, c["label_x"][1] + 45
        clip = fitz.Rect(x0, body[0], x1, body[1])
        for dpi in (300, 250):
            pix = page.get_pixmap(dpi=dpi, clip=clip, colorspace=fitz.csGRAY)
            sc = 72 / dpi
            for text, a, b, c2, d in winocr.ocr_pixmap(pix):
                toks.append((text, (a * sc + x0, b * sc + body[0], c2 * sc + x0, d * sc + body[0]), (d - b) * sc))
    return toks


def page_labels(page, cfg, pno=None, prev_last=None, info=None, toks=None, covered=()):
    """한 쪽의 문제 번호: [{"num", "label", "col", "x", "y0", "y1"}] (단 → 위에서 아래 순).
    prev_last: 앞 쪽의 마지막 번호 (빠진 번호 판단용). covered: 묶음이 이미 덮는 번호들.
    info(dict)에 offband / rescued 를 적어 준다."""
    pno = page.number if pno is None else pno
    cols = columns_for(cfg, pno)
    body = cfg.get("body") or [0, page.rect.height]
    if toks is None:
        toks = page_content(page, cfg)[0]
    labels, offband = _match_labels(toks, cfg, cols, body)
    labels = _dedup(labels)
    rescued = 0
    if cfg["source"] == "ocr" and cfg.get("rescue", True) and _has_gap(labels, prev_last, covered):
        more, _ = _match_labels(_rescue_tokens(page, cfg, cols, body), cfg, cols, body, slack=8)
        have = {d["num"] for d in labels}
        add = [d for d in more if d["num"] not in have]
        rescued = len({d["num"] for d in add})
        labels = _dedup(labels + add)
    if info is not None:
        info["offband"] = offband
        info["rescued"] = rescued
    return labels


def page_groups(lines, cfg, cols, body, pno):
    """묶음 머리글: [{"a", "b", "label", "col", "y0", "y1"}]. 단 왼쪽(label_x±10)에서 시작하는 '[a~b]' 줄."""
    if cfg.get("groups") is False:
        return []
    rx = re.compile(cfg.get("group_regex") or GROUP_REGEX)
    out = []
    for text, bbox in lines:
        m = rx.match(text)
        if not m or not (body[0] <= bbox[1] <= body[1]):
            continue
        a, b = int(m.group(1)), int(m.group(2))
        if b < a or b > a + 30:                           # 닫는 괄호 ']' 를 '1' 로 읽은 경우 등: 앞자리 수만큼만
            b = int(m.group(2)[:len(m.group(1))])
        if not (a < b <= a + 30):
            continue
        ci = next((i for i, c in enumerate(cols) if c["label_x"][0] - 10 <= bbox[0] <= c["label_x"][1] + 10), None)
        if ci is None:
            continue
        w = len(m.group(1))
        out.append({"a": a, "b": b, "label": f"{a:0{w}d}~{b:0{w}d}", "col": ci,
                    "y0": round(bbox[1], 1), "y1": round(bbox[3], 1)})
    for mg in cfg.get("manual_groups", []):
        if mg["page"] == pno + 1:
            a, b = mg["range"]
            out.append({"a": a, "b": b, "label": f"{a}~{b}*", "col": mg["col"], "y0": mg["y"], "y1": mg["y"] + 10})
    out.sort(key=lambda g: (g["col"], g["y0"]))
    dedup = []
    for g in out:
        if dedup and dedup[-1]["col"] == g["col"] and (abs(dedup[-1]["y0"] - g["y0"]) < 8
                                                       or (dedup[-1]["a"], dedup[-1]["b"]) == (g["a"], g["b"])):
            continue
        dedup.append(g)
    return dedup


# ---------------------------------------------------------------- 영역 자르기

def content_bottom(gray, scale, x0, x1, y_top, y_limit, gap_stop):
    """[x0,x1]×[y_top,y_limit] 안에서 위에서부터 이어지는 내용의 바닥 y(pt). 큰 여백을 만나면 멈춤."""
    w = gray.width
    px0, px1 = max(0, int(x0 * scale)), min(w, int(x1 * scale))
    ry0, ry1 = max(0, int(y_top * scale)), min(gray.height, int(y_limit * scale))
    s, stride = gray.samples, gray.stride
    last, blank, started = ry0, 0, False
    stop = gap_stop * scale
    for ry in range(ry0, ry1):
        row = s[ry * stride + px0: ry * stride + px1]
        if min(row, default=255) < 150:                   # 충분히 어두운 점이 있으면 내용
            last, blank, started = ry, 0, True
        elif started:
            blank += 1
            if blank >= stop:
                break
    return last / scale


def extract(pdf_path, cfg, only_pages=None, progress=None):
    """→ (problems, report). problems 는 core.books.register 에 그대로 넣을 수 있는 형식."""
    doc = fitz.open(pdf_path)
    pages = page_list(cfg, doc.page_count, only_pages)
    problems, empty_pages, offband_pages, rescued, n_groups = [], [], [], 0, 0
    prev_last = None
    for k, pno in enumerate(pages):
        page = doc[pno]
        cols = columns_for(cfg, pno)
        body = cfg.get("body") or [0, page.rect.height]
        toks, lines = page_content(page, cfg)
        groups = page_groups(lines, cfg, cols, body, pno)
        if cfg["source"] == "ocr" and cfg.get("groups") is not False and                 (groups or _match_labels(toks, cfg, cols, body)[1] >= 2):
            # 묶음 쪽으로 보이면 머리글만 한 번 더 높은 해상도로 (작은 색 글씨 머리글을 놓치지 않게)
            hi = _ocr_page(page, {**cfg, "ocr_dpi": [300]})[1]
            groups = page_groups(lines + hi, cfg, cols, body, pno)
        covered = {n for g in groups for n in range(g["a"], g["b"] + 1)}
        info = {}
        labels = page_labels(page, cfg, pno, prev_last, info, toks=toks, covered=covered)
        manual = [m for m in cfg.get("manual_labels", []) if m["page"] == pno + 1]
        if manual:                                          # OCR 로 끝내 못 읽은 번호를 사람이 넣은 것
            have = {d["num"] for d in labels}
            labels = _dedup(labels + [{"num": m["num"], "label": f"{m['num']}*", "col": m["col"],
                                       "x": 0, "y0": m["y"], "y1": m["y"] + 10}
                                      for m in manual if m["num"] not in have])
        rescued += info.get("rescued", 0)
        if info.get("offband", 0) >= 2 and not groups:
            offband_pages.append(pno + 1)
        if progress:
            progress(k + 1, len(pages), pno + 1, len(labels) + len(groups))
        if not labels and not groups:
            empty_pages.append(pno + 1)
            continue
        last = max(labels + [{"num": g["b"], "col": g["col"], "y0": g["y0"]} for g in groups],
                   key=lambda d: (d["col"], d["y0"]))
        prev_last = last["num"]
        gray = page.get_pixmap(dpi=TRIM_DPI, colorspace=fitz.csGRAY)
        scale = TRIM_DPI / 72
        for ci, col in enumerate(cols):
            ev = sorted([("L", d["y0"], d) for d in labels if d["col"] == ci]
                        + [("G", g["y0"], g) for g in groups if g["col"] == ci], key=lambda e: e[1])
            used = set()
            for i, (kind, y0, d) in enumerate(ev):
                if i in used:
                    continue
                top = max(body[0], y0 - cfg["top_pad"])
                if kind == "G":                             # 묶음: 범위 안 번호들은 같이 먹는다
                    j = i + 1
                    while j < len(ev) and ev[j][0] == "L" and d["a"] <= ev[j][2]["num"] <= d["b"]:
                        used.add(j)
                        j += 1
                    limit = ev[j][1] - cfg["top_pad"] - 2 if j < len(ev) else body[1]
                    gap = cfg.get("group_gap_stop", cfg["gap_stop"])
                else:
                    limit = ev[i + 1][1] - cfg["top_pad"] - 2 if i + 1 < len(ev) else body[1]
                    gap = cfg["gap_stop"]
                bot = min(limit, content_bottom(gray, scale, col["x"][0], col["x"][1], top, limit, gap)
                          + cfg["bot_pad"])
                item = {"num": d["a"] if kind == "G" else d["num"], "label": d["label"],
                        "page": pno + 1, "pdf_page": pno,
                        "column": "LR"[ci] if len(cols) == 2 else str(ci),
                        "bbox": [round(col["x"][0], 1), round(top, 1), round(col["x"][1], 1), round(bot, 1)]}
                if kind == "G":
                    item["num_end"] = d["b"]
                    n_groups += 1
                problems.append(item)
    doc.close()
    dropped = []
    if cfg.get("drop_outliers", True):
        problems, dropped = drop_outliers(problems)
    rep = make_report(problems, pages, empty_pages)
    rep["dropped"] = dropped
    rep["offband_pages"] = offband_pages
    rep["rescued"] = rescued
    rep["groups"] = n_groups
    return problems, rep


# ---------------------------------------------------------------- 점검

def make_report(problems, pages, empty_pages):
    nums = [p["num"] for p in problems]
    gaps, dups, backs = [], [], []
    for a, b in zip(problems, problems[1:]):
        ae = a.get("num_end", a["num"])                     # 묶음이면 끝 번호
        if b["num"] == ae + 1:
            continue
        if b["num"] == a["num"]:
            dups.append((a["page"], a["num"]))
        elif ae < b["num"] <= ae + 30:
            gaps.append((a["page"], ae, b["num"]))           # 사이 번호가 빠짐 (OCR 놓침 가능)
        else:
            backs.append((a["page"], a["num"], b["page"], b["num"]))   # 번호가 새로 시작/점프 (단원 바뀜일 수도)
    heights = sorted(p["bbox"][3] - p["bbox"][1] for p in problems)
    tiny = [(p["page"], p["num"]) for p in problems if p["bbox"][3] - p["bbox"][1] < 25]
    return {
        "pages_scanned": len(pages), "problems": len(problems),
        "pages_without_labels": empty_pages,
        "gaps": gaps, "duplicates": dups, "jumps": backs, "too_small": tiny,
        "height_median": heights[len(heights) // 2] if heights else None,
        "first_last": [nums[:3], nums[-3:]] if nums else [],
    }


def report_text(rep):
    lines = [f"쪽 {rep['pages_scanned']}개 처리, 문제 {rep['problems']}개 (높이 중간값 {rep['height_median']}pt)",
             f"처음/끝 번호: {rep['first_last']}"]
    if rep["gaps"]:
        lines.append(f"⚠ 빠진 번호 {len(rep['gaps'])}곳: " + ", ".join(f"{p}쪽 {a}→{b}" for p, a, b in rep["gaps"][:30]))
    if rep["duplicates"]:
        lines.append(f"⚠ 중복 번호 {len(rep['duplicates'])}곳: " + ", ".join(f"{p}쪽 {n}" for p, n in rep["duplicates"][:30]))
    if rep["jumps"]:
        lines.append(f"ℹ 번호 새로 시작/점프 {len(rep['jumps'])}곳: "
                     + ", ".join(f"{p1}쪽 {a}→{p2}쪽 {b}" for p1, a, p2, b in rep["jumps"][:30]))
    if rep["too_small"]:
        lines.append(f"⚠ 너무 작은 영역 {len(rep['too_small'])}개: " + ", ".join(f"{p}쪽 {n}" for p, n in rep["too_small"][:30]))
    if rep.get("dropped"):
        lines.append(f"ℹ 튀는 번호로 보고 뺀 것 {len(rep['dropped'])}개: " + ", ".join(f"{p}쪽 {n}" for p, n in rep["dropped"][:30]))
    if rep.get("groups"):
        lines.append(f"ℹ 묶음 문제 {rep['groups']}개 (머리글부터 소문제 끝까지 하나로)")
    if rep.get("rescued"):
        lines.append(f"ℹ 다시 읽어서 찾은 번호 {rep['rescued']}개")
    if rep.get("offband_pages"):
        ob = rep["offband_pages"]
        lines.append(f"⚠ 번호 영역 밖에 번호 모양이 많은 쪽 {len(ob)}개 (묶음문제·다른 배치?): {ob[:60]}{' …' if len(ob) > 60 else ''}")
    if rep["pages_without_labels"]:
        pw = rep["pages_without_labels"]
        lines.append(f"ℹ 번호 없는 쪽 {len(pw)}개: {pw[:60]}{' …' if len(pw) > 60 else ''}")
    return "\n".join(lines)


def contact_sheets(pdf_path, problems, out_dir, per_sheet=12, width_pt=260, dpi=80, prefix="sheet"):
    """잘린 문제들을 번호와 함께 한 장에 모은 PNG (눈으로 검수용). 반환: 파일 경로 목록"""
    os.makedirs(out_dir, exist_ok=True)
    doc = fitz.open(pdf_path)
    paths = []
    cols = 3
    for s in range(0, len(problems), per_sheet):
        chunk = problems[s:s + per_sheet]
        cell_w = width_pt + 20
        rows = []
        for p in chunk:
            r = fitz.Rect(*p["bbox"])
            h = r.height * min(1.0, width_pt / r.width) + 22
            rows.append(h)
        row_h = [max(rows[i:i + cols]) for i in range(0, len(rows), cols)]
        sheet = fitz.open()
        pg = sheet.new_page(width=cell_w * cols, height=sum(row_h) + 10)
        y = 5
        for ri in range(len(row_h)):
            for ci in range(cols):
                i = ri * cols + ci
                if i >= len(chunk):
                    break
                p = chunk[i]
                r = fitz.Rect(*p["bbox"])
                sc = min(1.0, width_pt / r.width)
                x = ci * cell_w + 10
                pg.insert_text((x, y + 12), f"{p['page']}p #{p['num']} ({p['label']})", fontsize=10, color=(0.8, 0, 0))
                dest = fitz.Rect(x, y + 16, x + r.width * sc, y + 16 + r.height * sc)
                pg.draw_rect(dest, color=(0.2, 0.4, 1), width=0.8)
                # 선생님 앱과 똑같이 get_pixmap(clip) 로 자른다 (show_pdf_page 는 쪽 회전을 반영하지 않아
                # 회전된 PDF 에서 모아보기가 뒤집혀 보였음)
                pix = ready_page(doc, p["pdf_page"], p.get("clean")).get_pixmap(dpi=max(dpi * 2, 144), clip=r)
                pg.insert_image(dest, pixmap=pix)
            y += row_h[ri]
        path = os.path.join(out_dir, f"{prefix}_{s // per_sheet + 1:03d}.png")
        pg.get_pixmap(dpi=dpi).save(path)
        paths.append(path)
    doc.close()
    return paths
