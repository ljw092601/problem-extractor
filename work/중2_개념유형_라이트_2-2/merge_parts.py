# -*- coding: utf-8 -*-
# python merge.py <slug_dir> <sub1> <sub2> ... [--bynum sub]
#   slug_dir/_<sub>/problems.json 을 합쳐 slug_dir/problems.json, report.txt
#   기본 정렬: (쪽, 단, y). --bynum 으로 준 sub 의 쪽은 (쪽, 번호) 순 (좌우 짝 배치 쪽)
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
args = sys.argv[1:]
bynum = set()
while "--bynum" in args:
    i = args.index("--bynum"); bynum.add(args[i + 1]); del args[i:i + 2]
root, subs = args[0], args[1:]
# (중2 라이트 2-2) --pdf 로 원본을 주면 쪽 가운데 '유형' 상자(전체 폭) 위아래를 띠로 나눠 띠 → 단 → y 순으로 정렬
pdfpath = None
if "--pdf" in args:
    i = args.index("--pdf"); pdfpath = args[i + 1]; del args[i:i + 2]
    root, subs = args[0], args[1:]
bands = {}
if pdfpath:
    import fitz
    _d = fitz.open(pdfpath)
    for _i, _pg in enumerate(_d, 1):
        bands[_i] = sorted(l["bbox"][1] for b in _pg.get_text("dict")["blocks"] for l in b.get("lines", [])
                           if "".join(s["text"] for s in l["spans"]).strip() == "유형"
                           and l["spans"][0]["font"].startswith("OTGongjungjeonhwa"))
allp, reps, pdfname = [], [], None
for s in subs:
    with open(os.path.join(root, "_" + s, "problems.json"), encoding="utf-8") as f:
        d = json.load(f)
    pdfname = d["pdf"]
    for p in d["problems"]:
        p["_bynum"] = s in bynum
    allp.extend(d["problems"])
    with open(os.path.join(root, "_" + s, "report.txt"), encoding="utf-8") as f:
        reps.append(f"===== layout_{s}.json ({len(d['problems'])}개) =====\n" + f.read().strip())
order = {"L": 0, "0": 0, "R": 1, "1": 1}
def key(p):
    if p["_bynum"]:
        return (p["page"], 0, 0, p["num"], p["bbox"][1])
    band = sum(1 for y in bands.get(p["page"], []) if y < p["bbox"][1])
    return (p["page"], band, order.get(p["column"], 0), p["bbox"][1], 0)
allp.sort(key=key)
# continued 조각은 같은 번호의 앞 문제 바로 뒤로 옮김
for c in [p for p in allp if p.get("continued")]:
    allp.remove(c)
    j = max(i for i, p in enumerate(allp) if p["num"] == c["num"] and not p.get("continued")
            and (p["page"], p["bbox"][1]) <= (c["page"], 9999) and p["page"] >= c["page"] - 1)
    while j + 1 < len(allp) and allp[j + 1].get("continued") and allp[j + 1]["num"] == c["num"]:
        j += 1
    allp.insert(j + 1, c)
for p in allp:
    del p["_bynum"]
    if p["page"] == 95 and p["num"] == 3 and p["column"] == "L" and "중2" in os.path.abspath(root):
        p["continued"] = True          # 94쪽 [2~3] 묶음의 3번이 다음 쪽 왼쪽 위로 넘어감
# 등록(core.books.merge_continued)은 '다른 단·쪽에 같은 번호가 연달아 오면 이어진 조각'으로 보고 합친다.
# 번호가 우연히 같은 서로 다른 문제(예제 7 → 다음 쪽 유제 7 등)가 합쳐지지 않게 앞 항목에 num_end = num 을 붙인다.
guarded = []
for a, b in zip(allp, allp[1:]):
    if (b["num"] == a["num"] and not a.get("num_end") and not b.get("num_end") and not b.get("continued")
            and (a["page"], a["column"]) != (b["page"], b["column"])):
        a["num_end"] = a["num"]
        guarded.append((a["page"], a["num"], b["page"]))
if guarded:
    print("num_end=num 붙임:", guarded)
ng = sum(1 for p in allp if p.get("num_end", p["num"]) > p["num"])
nc = sum(1 for p in allp if p.get("continued"))
with open(os.path.join(root, "problems.json"), "w", encoding="utf-8") as f:
    json.dump({"pdf": pdfname, "problems": allp}, f, ensure_ascii=False, indent=1)
with open(os.path.join(root, "report.txt"), "w", encoding="utf-8") as f:
    f.write("\n\n".join(reps) + f"\n\n===== 합침 =====\n항목 {len(allp)}개 (묶음 {ng}개, 이어진 조각 {nc}개)\n")
print("total", len(allp), "groups", ng, "continued", nc)
# 등록 때 잘못 합쳐지는지는 mc_check.py 로 확인
