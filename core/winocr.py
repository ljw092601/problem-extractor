# -*- coding: utf-8 -*-
"""
Windows 내장 OCR (Windows.Media.Ocr) — 스캔본 교재에서 문제 번호를 읽을 때 쓴다.
관리자 PC(등록 작업)에서만 쓰며, 선생님용 exe 에는 들어가지 않는다.

    words = ocr_pixmap(pix, lang="en-US")   # [(text, x0, y0, x1, y1)]  (픽셀 좌표)
"""
import asyncio

import fitz
from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import BitmapPixelFormat, SoftwareBitmap
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter

_engines = {}


def _engine(lang):
    if lang not in _engines:
        eng = OcrEngine.try_create_from_language(Language(lang))
        if eng is None:
            raise RuntimeError(f"Windows OCR 언어가 설치되어 있지 않아요: {lang}")
        _engines[lang] = eng
    return _engines[lang]


def _to_bitmap(pix):
    if pix.n != 4:                                        # BGRA 8비트로 맞춘다
        pix = fitz.Pixmap(fitz.csRGB, pix) if pix.colorspace != fitz.csRGB else pix
        pix = fitz.Pixmap(pix, 1)                         # 알파 채널 추가
    # PyMuPDF 는 RGBA → OCR 은 BGRA 를 기대하지만 글자 인식에는 채널 순서가 무관
    w = DataWriter()
    w.write_bytes(bytes(pix.samples))
    buf = w.detach_buffer()
    return SoftwareBitmap.create_copy_from_buffer(buf, BitmapPixelFormat.BGRA8, pix.width, pix.height)


async def _recognize(pix, lang):
    result = await _engine(lang).recognize_async(_to_bitmap(pix))
    out = []
    for line in result.lines:
        for word in line.words:
            r = word.bounding_rect
            out.append((word.text, r.x, r.y, r.x + r.width, r.y + r.height))
    return out


def ocr_pixmap(pix, lang="en-US"):
    """fitz.Pixmap → [(글자, x0, y0, x1, y1)] 픽셀 좌표."""
    return asyncio.run(_recognize(pix, lang))


async def _recognize_lines(pix, lang):
    result = await _engine(lang).recognize_async(_to_bitmap(pix))
    out = []
    for line in result.lines:
        words = [(w.text, w.bounding_rect.x, w.bounding_rect.y, w.bounding_rect.x + w.bounding_rect.width,
                  w.bounding_rect.y + w.bounding_rect.height) for w in line.words]
        if words:
            out.append((line.text, min(w[1] for w in words), min(w[2] for w in words),
                        max(w[3] for w in words), max(w[4] for w in words), words))
    return out


def ocr_lines(pix, lang="en-US"):
    """fitz.Pixmap → [(줄 글자, x0, y0, x1, y1, 단어들)] 픽셀 좌표 (OCR 이 묶은 줄 단위).
    단어들 = [(글자, x0, y0, x1, y1)]"""
    return asyncio.run(_recognize_lines(pix, lang))


def max_image_side():
    return OcrEngine.max_image_dimension
