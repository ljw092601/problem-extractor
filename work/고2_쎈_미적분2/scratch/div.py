import fitz, json
d=fitz.open('work/_src/고2/쎈/2022개정 쎈 미적분2 본책.pdf')
out={}
for pn in range(9,192):
    pg=d[pn-1]; pix=pg.get_pixmap(dpi=72,colorspace=fitz.csGRAY,clip=fitz.Rect(0,60,595,780))
    w,h=pix.width,pix.height; s=pix.samples
    lc=[sum(1 for y in range(h) if s[y*w+x]<225) for x in range(w)]
    dc=[sum(1 for y in range(h) if s[y*w+x]<160) for x in range(w)]
    div=max(range(265,330),key=lambda x:lc[x])
    ink=min(x for x in range(w) if dc[x]>3)
    out[pn]=(div if lc[div]>300 else None, lc[div], ink)
    print(pn,out[pn])
json.dump(out,open('work/고2_쎈_미적분2/scratch/div.json','w'))
