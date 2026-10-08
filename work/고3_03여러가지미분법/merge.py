"""layout 3개(0/A/B)의 extract 결과를 합쳐 최종 problems.json / layout.json / report.txt 를 만든다.
python merge.py <scratch dir> <out dir>"""
import json, sys
S, OUT = sys.argv[1], sys.argv[2]
allp, lays, reps = [], {}, []
for n in ("0", "A", "B"):
    data = json.load(open(f"{S}/x{n}/problems.json", encoding="utf-8"))
    pdfname = data["pdf"]
    for p in data["problems"]:
        p["kind"] = n
    allp += data["problems"]
    lays[n] = json.load(open(f"{S}/layout_{n}.json", encoding="utf-8"))
    reps.append(f"[{n}] " + open(f"{S}/x{n}/report.txt", encoding="utf-8").read().strip())
# 손본 것: 7쪽 문제 3 — 왼쪽 여백 설명('Pa은 압력을 …')이 겹쳐서 왼쪽 끝을 본문 시작으로
for p in allp:
    if p["kind"] == "A" and p["page"] == 7 and p["num"] == 3:
        p["bbox"][0] = 158
allp.sort(key=lambda p: (p["page"], p["column"], p["bbox"][1]))
for p in allp:
    p.pop("kind")
json.dump({"pdf": pdfname, "problems": allp}, open(f"{OUT}/problems.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"source": "text", "note": "종류별 layout 3개로 따로 추출해 합침 (0=배운 내용 확인하기, A=본문 문제, B=스스로 확인하기/마무리하기)",
           "parts": lays}, open(f"{OUT}/layout.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
open(f"{OUT}/report.txt", "w", encoding="utf-8").write("\n\n".join(reps) + f"\n\n합계 {len(allp)}문제\n")
print(len(allp))
