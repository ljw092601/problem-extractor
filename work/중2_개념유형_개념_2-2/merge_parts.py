# -*- coding: utf-8 -*-
# python merge_parts.py <slug_dir> <sub1> <sub2> ...
#   slug_dir/_<sub>/problems.json 을 합쳐 slug_dir/problems.json, report.txt  (정렬: 쪽, 단, y)
#   label_kinds.json 이 있으면 _concept 에서는 '필수', _yuje 에서는 '유제' 번호의 항목만 남긴다
#   (두 레이아웃 모두 번호를 전부 넣어 영역이 다음 번호에서 끊기게 했기 때문).
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
root, subs = sys.argv[1], sys.argv[2:]
kinds = {}
kp = os.path.join(root, "label_kinds.json")
top_pad = 8
if os.path.exists(kp):
    kd = json.load(open(kp, encoding="utf-8"))
    if isinstance(kd, dict):
        top_pad, kd = kd["top_pad"], kd["labels"]
    for page, y, k in kd:
        kinds.setdefault(page, []).append((y, k))
want = {"concept": "필수", "yuje": "유제"}

def kind_of(p):
    ls = kinds.get(p["page"], [])
    if not ls:
        return None
    y0 = p["bbox"][1]
    return min(ls, key=lambda t: abs(t[0] - y0 - top_pad))[1]

lx, lx_pad, nfix = {}, 1.5, [0]
lxp = os.path.join(root, "label_x.json")
if os.path.exists(lxp):
    lx = json.load(open(lxp, encoding="utf-8"))
    lx_pad = lx.pop("pad")
allp, reps, pdfname = [], [], None
for s in subs:
    with open(os.path.join(root, "_" + s, "problems.json"), encoding="utf-8") as f:
        d = json.load(f)
    pdfname = d["pdf"]
    ps = d["problems"]
    if s in want and kinds:
        ps = [p for p in ps if kind_of(p) == want[s]]
    if s in lx:                                          # 왼쪽 옆날개 빼기: bbox 왼쪽 = 번호 x - pad
        tp = json.load(open(os.path.join(root, f"layout_{s}.json"), encoding="utf-8"))["top_pad"]
        for p in ps:
            ls = [t for t in lx[s] if t[0] == p["page"]]
            if ls:
                t = min(ls, key=lambda t: abs(t[1] - p["bbox"][1] - tp))
                if abs(t[1] - p["bbox"][1] - tp) < 6:
                    p["bbox"][0] = round(max(p["bbox"][0], t[2] - lx_pad), 1)
                    nfix[0] += 1
    allp.extend(ps)
    with open(os.path.join(root, "_" + s, "report.txt"), encoding="utf-8") as f:
        reps.append(f"===== layout_{s}.json (남긴 항목 {len(ps)}개) =====\n" + f.read().strip())
order = {"L": 0, "0": 0, "R": 1, "1": 1}
allp.sort(key=lambda p: (p["page"], order.get(p["column"], 0), p["bbox"][1]))
# 등록(core.books.merge_continued)은 '다른 단·쪽에 같은 번호가 연달아 오면 이어진 조각'으로 보고 합친다.
# 번호가 우연히 같은 서로 다른 문제가 합쳐지지 않게 앞 항목에 num_end = num 을 붙인다.
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
print("x0 fixed", nfix[0]); print("total", len(allp), "groups", ng, "continued", nc)
