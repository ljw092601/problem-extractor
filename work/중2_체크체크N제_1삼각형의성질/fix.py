# -*- coding: utf-8 -*-
"""extract 결과에 손 보정: trim(묶음 아래 다음 소단원 띠 떼기), extend(마지막 쪽 소문항까지), cont(단 넘어간 묶음 조각)
usage: python fix.py <extract dir> <pdf> <out problems.json> <spec.json>"""
import json, sys, fitz
sys.path.insert(0, r"C:\Users\ljw09\Desktop\promblem_area")
from core.extract import content_bottom
d, pdf, out, spec = sys.argv[1:5]
spec = json.load(open(spec, encoding='utf-8'))
data = json.load(open(d + '/problems.json', encoding='utf-8'))
ps = data['problems']
doc = fitz.open(pdf)
def gray(pno):
    return doc[pno].get_pixmap(dpi=100, colorspace=fitz.csGRAY)
sc = 100 / 72
log = []
for lab, gap in spec.get('trim', []):
    p = next(q for q in ps if q['label'] == lab)
    x0, y0, x1, y1 = p['bbox']
    nb = round(min(y1, content_bottom(gray(p['pdf_page']), sc, x0, x1, y0, y1, gap) + 6), 1)
    log.append(f"trim {lab}: {y1} -> {nb}"); p['bbox'][3] = nb
for lab, gap, lim in spec.get('extend', []):
    p = next(q for q in ps if q['label'] == lab)
    x0, y0, x1, y1 = p['bbox']
    nb = round(min(lim, content_bottom(gray(p['pdf_page']), sc, x0, x1, y0, lim, gap) + 6), 1)
    log.append(f"extend {lab}: {y1} -> {nb}"); p['bbox'][3] = nb
for c in spec.get('cont', []):
    i = next(k for k, q in enumerate(ps) if q['label'] == c['after'])
    prev = ps[i]
    x0, x1 = c['x']; y0, lim = c['y']
    nb = round(min(lim, content_bottom(gray(c['page'] - 1), sc, x0, x1, y0, lim, 45) + 6), 1)
    item = {"num": prev['num'], "label": prev['label'], "page": c['page'], "pdf_page": c['page'] - 1,
            "column": c['column'], "bbox": [x0, y0, x1, nb], "continued": True}
    if 'num_end' in prev: item['num_end'] = prev['num_end']
    ps.insert(i + 1, item); log.append(f"cont after {c['after']}: p{c['page']} {item['bbox']}")
for m in spec.get('manual_bbox', []):
    p = next(q for q in ps if q['label'] == m['label'] and q['page'] == m['page'])
    log.append(f"bbox {m['label']}: {p['bbox']} -> {m['bbox']}"); p['bbox'] = m['bbox']
data['problems'] = ps
json.dump(data, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print("\n".join(log)); print(len(ps))
