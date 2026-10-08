import json,sys
src,dst=sys.argv[1],sys.argv[2]
D=json.load(open(src,encoding='utf-8'))
ps=D['problems']; out=[]
def find(page,col,label):
    return next(p for p in ps if p['page']==page and p['column']==col and p['label']==label)
for p in ps:
    if 2<=p['page']<=22 and p['bbox'][1]<118: p['bbox'][1]=118.0
    if p['label'].endswith('*'):
        n=p['num']; lab=p['label'][:-1]
        # 모의고사: 왼쪽 단·오른쪽 단 01~20, 서술형(오른쪽 단 116/119.. 쪽) 1~4
        p['label']=lab if (p['column']=='R' and (p['page']-113)%3==0) else f"{n:02d}"
    out.append(p)
# 9쪽 R12~R15, 11쪽 R11·R13 → 앞 묶음에서 넘어간 조각 하나로
def combine(page,col,labels):
    items=[find(page,col,l) for l in labels]
    first=items[0]
    first['bbox'][3]=items[-1]['bbox'][3]; first['continued']=True
    for it in items[1:]: out.remove(it)
combine(9,'R',['12','13','14','15'])
combine(11,'R',['11','13'])
for pg,l in [(5,'11'),(14,'08'),(15,'11')]:
    find(pg,'R',l)['continued']=True
find(30,'L','02')['bbox'][3]=489.0  # 아래 '유형 02' 띠 빼기
D['problems']=out
json.dump(D,open(dst,'w',encoding='utf-8'),ensure_ascii=False,indent=1)
print(len(out))
