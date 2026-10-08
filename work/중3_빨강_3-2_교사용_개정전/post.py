"""extract 결과 손질: 옆 단·다음 쪽으로 넘어간 묶음의 소문제들을 조각 하나로 합치고 continued 표시.
사용: python post.py <extract 의 problems.json> <최종 problems.json>
"""
import json, sys
src, dst = sys.argv[1], sys.argv[2]
D = json.load(open(src, encoding='utf-8'))
ps = D['problems']
out = []
for p in ps:
    prev = out[-1] if out else None
    # 앞 항목이 (다른 단의) 묶음 [a~b] 이고 이 번호가 그 범위 안 → 넘어간 조각
    grp = None
    for q in reversed(out):
        if not q.get('continued'):
            grp = q
            break
    if (grp and grp.get('num_end') and not p.get('num_end')
            and (p['page'], p['column']) != (grp['page'], grp['column'])
            and grp['num'] < p['num'] <= grp['num_end']):
        if prev.get('continued') and (prev['page'], prev['column']) == (p['page'], p['column']):
            prev['bbox'][3] = max(prev['bbox'][3], p['bbox'][3])   # 같은 단의 다음 소문제 → 한 조각으로
            continue
        p['continued'] = True
    out.append(p)
def find(page, col, label):
    return next(p for p in out if p['page'] == page and p['column'] == col and p['label'] == label)
for p in out:
    # 계산력 쪽(2~22): 제목 띠 아랫부분이 딸려 오지 않게 윗끝을 118 아래로 (지금은 해당 없음)
    if 2 <= p['page'] <= 22 and 90 < p['bbox'][1] < 118:
        p['bbox'][1] = 118.0
# 두 줄짜리 '유형' 띠 제목의 둘째 줄이 문제 윗부분에 딸려 오던 것 → 윗끝을 그 줄 아래로
for (pg, col, lab), top in {
    # 값 = 번호 글자 윗끝(그림으로 잰 값) - 0.25
    (29, 'L', '01'): 177.0, (41, 'L', '03'): 514.5, (41, 'R', '05'): 140.5, (43, 'L', '17'): 109.25,
    (43, 'R', '21'): 109.25, (45, 'R', '36'): 110.2, (47, 'L', '08'): 110.0, (47, 'L', '10'): 480.8,
    (60, 'R', '44'): 109.25, (60, 'R', '46'): 498.75, (61, 'L', '48'): 109.25, (61, 'R', '52'): 109.25,
    (61, 'R', '54'): 500.1, (62, 'L', '56'): 109.25,
}.items():
    find(pg, col, lab)['bbox'][1] = float(top)
D['problems'] = out
json.dump(D, open(dst, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(len(ps), '->', len(out), 'continued', sum(1 for p in out if p.get('continued')))
