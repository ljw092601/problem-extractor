# 문제 영역 아래로 딸려 온 소제목 띠(흰 DIN-Bold 12 번호 + 제목) 위에서 자르기
import fitz,json,sys
doc=fitz.open(r"work/_src/고3/고등_미적분_2021자이스토리(고2)_문제지.pdf")
src,dst=sys.argv[1],sys.argv[2]
data=json.load(open(src,encoding="utf-8"))
heads={}
def get(pn):
    if pn not in heads:
        hs=[]
        for b in doc[pn].get_text("dict")["blocks"]:
            for l in b.get("lines",[]):
                sp=[s for s in l["spans"] if s["text"].strip()]
                if sp and sp[0]["font"].replace("-","")=="DINBold" and round(sp[0]["size"])==12 and sp[0]["color"]==0xffffff:
                    hs.append(l["bbox"])
        heads[pn]=hs
    return heads[pn]
n=0
for p in data["problems"]:
    x0,y0,x1,y1=p["bbox"]
    for hb in get(p["pdf_page"]):
        if x0-5<=hb[0]<=x1 and y0+15<hb[1]<y1:
            nb=round(hb[1]-6,1)
            if nb<p["bbox"][3]:
                print("trim",p["page"],p["column"],p["label"],p["bbox"][3],"->",nb); p["bbox"][3]=nb; n+=1
    for hb in get(p["pdf_page"]):
        if x0-5<=hb[0]<=x1 and hb[3]+3>p["bbox"][1] and hb[1]<p["bbox"][1]+15:
            nt=round(hb[3]+3,1); print("top",p["page"],p["label"],p["bbox"][1],"->",nt); p["bbox"][1]=nt; n+=1
json.dump(data,open(dst,"w",encoding="utf-8"),ensure_ascii=False,indent=1)
print("trimmed",n)
