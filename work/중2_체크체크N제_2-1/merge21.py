# -*- coding: utf-8 -*-
"""본문(layout.json → fix.py 보정) + 부록(layout_app.json) problems.json 을 쪽 → 단(L→R) → y 순으로 합침
usage: python merge21.py <본문 보정 결과 폴더> <부록 결과 폴더> <out dir>"""
import json,os,sys
a,b,o=sys.argv[1:4]
pa=json.load(open(a+'/problems.json',encoding='utf-8'))
pb=json.load(open(b+'/problems.json',encoding='utf-8'))['problems']
allp=pa['problems']+pb
allp.sort(key=lambda p:(p['page'],{'L':0,'R':1}[p['column']],p['bbox'][1]))
pa['problems']=allp
json.dump(pa,open(o+'/problems.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
rep="== 본문 (layout.json, 보정 전 report)\n"+open(a+'/report.txt',encoding='utf-8').read()+"\n\n== 부록 (layout_app.json)\n"+open(b+'/report.txt',encoding='utf-8').read()
open(o+'/report.txt','w',encoding='utf-8').write(f"합계 {len(allp)}개 (본문 {len(pa['problems'])-len(pb)}, 부록 {len(pb)}, 묶음 {sum(1 for p in allp if 'num_end' in p)})\n\n"+rep)
print(len(allp))
