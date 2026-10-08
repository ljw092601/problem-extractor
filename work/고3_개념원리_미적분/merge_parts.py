# -*- coding: utf-8 -*-
# python merge_parts.py <slug폴더> <pdf>
#   _a/problems.json(익히기·연습·실력) + _b/problems.json(확인체크) → problems.json, report.txt
#   - 아래 끝을 그 쪽의 다음 '벽'(STEP 띠·필수예제 머리, barriers.json) 위로 자름
#   - 확인체크(B) 항목의 왼쪽 = 번호 x - 3 (왼쪽 '확인체크' 뱃지 빼기)
#   - 다른 쪽에 같은 번호가 우연히 이어 오면 등록 때 합쳐지지 않게 앞 항목에 num_end = num
import sys, json, os
sys.stdout.reconfigure(encoding="utf-8")
root = sys.argv[1]
bj = json.load(open(os.path.join(root, "barriers.json"), encoding="utf-8"))
bars, blx = bj["barriers"], bj["b_label_x"]
allp, reps, pdfname, ncut, nx, ntop = [], [], None, 0, 0, [0]
for s in ("a", "b"):
    d = json.load(open(os.path.join(root, "_" + s, "problems.json"), encoding="utf-8"))
    pdfname = d["pdf"]
    tp = json.load(open(os.path.join(root, f"layout_{s}.json"), encoding="utf-8"))["top_pad"]
    for p in d["problems"]:
        y0 = p["bbox"][1]
        ly = y0 + tp                                            # 번호 윗끝 (top_pad 로 올리기 전)
        pb = bars.get(str(p["page"]), [])
        nxt = [b[0] for b in pb if b[0] > ly + 2]
        if nxt and p["bbox"][3] > min(nxt) - 8:
            p["bbox"][3] = round(min(nxt) - 8, 1)
            ncut += 1
        above = [b[1] for b in pb if b[0] < ly - 2 and b[1] + 2 > y0]      # 바로 위 STEP 띠를 물면 아래로
        if above:
            p["bbox"][1] = round(min(ly - 1, max(above) + 2), 1)
            y0 = ly - tp
            ntop[0] += 1
        if s == "b":
            ls = blx.get(str(p["page"]), [])
            if ls:
                t = min(ls, key=lambda t: abs(t[0] - y0 - tp))
                if abs(t[0] - y0 - tp) < 3:
                    p["bbox"][0] = round(t[1] - 3, 1)
                    nx += 1
        allp.append(p)
    reps.append(f"===== layout_{s}.json ({len(d['problems'])}개) =====\n"
                + open(os.path.join(root, "_" + s, "report.txt"), encoding="utf-8").read().strip())
allp.sort(key=lambda p: (p["page"], p["bbox"][1]))
# 연한 회색 테두리 상자(보기·빈칸 채우기 상자)는 밝기 기준으로 '내용'이 아니라서 아래 테두리가 잘림
#   → 영역 안에서 시작해 아래로 나가는 그림(상자)이 있으면 그 아래 끝까지 늘림 (다음 문제 윗끝·본문 아래 끝까지만)
nbox = 0
if len(sys.argv) > 2:
    import fitz
    doc = fitz.open(sys.argv[2])
    body_bot = json.load(open(os.path.join(root, "layout_a.json"), encoding="utf-8"))["body"][1]
    for i, p in enumerate(allp):
        x0, y0, x1, y1 = p["bbox"]
        nxt = allp[i + 1] if i + 1 < len(allp) and allp[i + 1]["page"] == p["page"] else None
        lim = nxt["bbox"][1] - 1 if nxt else body_bot
        pb = [b[0] for b in bars.get(str(p["page"]), []) if b[0] > y0 + 14]
        if pb:
            lim = min(lim, min(pb) - 8)
        ext = y1
        for dr in doc[p["pdf_page"]].get_drawings():
            r = dr["rect"]
            if (r.x0 >= x0 - 2 and r.x1 <= x1 + 2 and y0 < r.y0 < y1 and y1 - 2 < r.y1 <= lim - 1
                    and r.width > 20):
                ext = max(ext, r.y1 + 3)
        if ext > y1:
            p["bbox"][3] = round(min(ext, lim), 1)
            nbox += 1
    print("box extended", nbox)
guarded = []
for a, b in zip(allp, allp[1:]):
    if b["num"] == a["num"] and not b.get("continued") and a["page"] != b["page"]:
        a["num_end"] = a["num"]
        guarded.append((a["page"], a["num"], b["page"]))
nc = sum(1 for p in allp if p.get("continued"))
json.dump({"pdf": pdfname, "problems": allp}, open(os.path.join(root, "problems.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
open(os.path.join(root, "report.txt"), "w", encoding="utf-8").write(
    "\n\n".join(reps) + f"\n\n===== 합침 =====\n항목 {len(allp)}개 (이어진 조각 {nc}개), 벽에서 자름 {ncut}, "
    f"확인체크 왼쪽 옮김 {nx}, 상자 아래 테두리까지 늘림 {nbox}, num_end=num {guarded}\n")
print("total", len(allp), "top", ntop[0], "cut", ncut, "xfix", nx, "guarded", guarded)
