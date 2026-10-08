# 벡터 번호 위치 찾기: 번호 앞 회색 '0' 글자(0 0 0 0.4 k) 위치
import fitz, json, sys
from collections import Counter
C = r"C:\Users\ljw09\AppData\Local\Temp\claude\C--Users-ljw09-Desktop-promblem-area\c26382be-0e2b-44d9-be28-6fa123aea8e4\scratchpad\rpm\clean\22개정 RPM 미적분1 학생용 1.pdf"
d = fitz.open(C)
out = []
stats = Counter()
for pno in range(len(d)):
    pg = d[pno]
    hits = []
    for dr in pg.get_drawings():
        f = dr.get("fill")
        if not f or abs(f[0] - 0.655) > 0.01 or abs(f[2] - 0.673) > 0.01:
            continue
        r = dr["rect"]
        if not (7.5 < r.height < 10 and 4 < r.width < 8):
            continue
        stats[round(r.x0)] += 1
        hits.append(r)
    # 한 번호 = 같은 y 에서 가장 왼쪽 글자
    hits.sort(key=lambda r: (round(r.y0), r.x0))
    seen = []
    for r in hits:
        if any(abs(r.y0 - s.y0) < 2 and abs(r.x0 - s.x0) < 20 for s in seen):
            continue
        seen.append(r)
    for r in seen:
        out.append({"page": pno + 1, "x": round(r.x0, 1), "y": round(r.y0, 1)})
json.dump(out, open(sys.argv[1], "w"), ensure_ascii=False)
print(len(out), sorted(stats.items())[:40])
