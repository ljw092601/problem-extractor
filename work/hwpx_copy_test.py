# -*- coding: utf-8 -*-
"""[시험] 한글 원본(hwpx)에서 문제 문단을 그대로 복사해 학원 양식 hwpx 에 붙인다 (그림 아닌 편집 가능한 글·수식).
    python work/hwpx_copy_test.py list  a.hwpx            # 찾은 문제 목록
    python work/hwpx_copy_test.py build out.hwpx a.hwpx:0,3 b.hwpx:1   # 파일:문제순번 들을 모아 만들기

방식
  - 문제 = 번호 상자(글상자 안 글자가 '01' 같은 두 자리 숫자)가 있는 문단부터 다음 번호 문단 전까지
  - 원본 header.xml 의 글꼴·테두리·글자 모양·탭·번호·문단 모양을 새 문서 header 뒤에 덧붙이고 번호(id)를 바꿔 단다
  - 그림(BinData)은 새 이름으로 복사, 문단의 줄 배치 캐시(linesegarray)는 지워 한글이 다시 계산하게 한다
"""
import copy
import io
import os
import re
import sys
import tempfile
import zipfile

from lxml import etree

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build_hwpx  # noqa: E402

NS = {"hp": "http://www.hancom.co.kr/hwpml/2011/paragraph",
      "hh": "http://www.hancom.co.kr/hwpml/2011/head",
      "hc": "http://www.hancom.co.kr/hwpml/2011/core",
      "hs": "http://www.hancom.co.kr/hwpml/2011/section",
      "opf": "http://www.idpf.org/2007/opf/"}
HP = "{%s}" % NS["hp"]
NUM_RE = re.compile(r"^\s*\d{1,2}\s*$")


def L(e):
    return etree.QName(e).localname


def rect_texts(p):
    """문단의 run 에 바로 붙은 글상자(rect)들의 글자."""
    out = []
    for r in p.findall(HP + "run"):
        for c in r:
            if L(c) == "rect":
                out.append("".join(t.text or "" for t in c.iter(HP + "t")))
    return out


def para_text(p):
    out = []
    for n in p.iter():
        if L(n) == "t" and n.text:
            out.append(n.text)
        elif L(n) == "script" and n.text:
            out.append("[" + n.text.strip() + "]")
    return "".join(out)


def find_problems(section):
    """[(label, [문단...])] — 번호 상자 문단이 들어 있는 모든 문단 목록(subList·sec)을 훑는다."""
    probs = []
    for holder in section.iter():
        kids = [c for c in holder if L(c) == "p"]
        starts = [i for i, p in enumerate(kids) if any(NUM_RE.match(t) for t in rect_texts(p))]
        for k, i in enumerate(starts):
            end = starts[k + 1] if k + 1 < len(starts) else len(kids)
            body = kids[i:end]
            while len(body) > 1 and not para_text(body[-1]).strip() and not body[-1].xpath(".//hp:pic|.//hp:tbl", namespaces=NS):
                body.pop()
            num = next(t for t in rect_texts(kids[i]) if NUM_RE.match(t)).strip()
            probs.append((num, body))
    return probs


class Merger:
    """새 문서(base) header 에 원본들의 서식 목록을 덧붙이고, 원본 번호 → 새 번호 표를 만든다."""
    LISTS = ["borderFills", "charProperties", "tabProperties", "numberings", "paraProperties"]

    def __init__(self, zdata):
        self.z = zipfile.ZipFile(io.BytesIO(zdata))
        self.files = {n: self.z.read(n) for n in self.z.namelist()}
        self.infos = {i.filename: i for i in self.z.infolist()}
        self.head = etree.fromstring(self.files["Contents/header.xml"])
        self.sec = etree.fromstring(self.files["Contents/section0.xml"])
        self.hpf = etree.fromstring(self.files["Contents/content.hpf"])
        self.maps = {}
        self.nbin = 0
        self.keep = {}

    def _list(self, head, name):
        return head.find(".//hh:refList/hh:" + name, NS)

    def add_source(self, key, src_zip):
        if key in self.maps:
            return self.maps[key]
        sh = etree.fromstring(src_zip.read("Contents/header.xml"))
        m = {"font": {}, "bf": {}, "cp": {}, "tab": {}, "num": {}, "pp": {}, "bin": {}}
        # 글꼴: 언어별로 같은 이름이면 기존 것, 없으면 뒤에 추가
        for sff in self._list(sh, "fontfaces"):
            lang = sff.get("lang")
            bff = next(f for f in self._list(self.head, "fontfaces") if f.get("lang") == lang)
            byname = {f.get("face"): f.get("id") for f in bff}
            m["font"][lang] = {}
            for f in sff:
                if f.get("face") in byname:
                    m["font"][lang][f.get("id")] = byname[f.get("face")]
                else:
                    nid = str(len(bff))
                    nf = copy.deepcopy(f); nf.set("id", nid); bff.append(nf)
                    byname[f.get("face")] = nid
                    m["font"][lang][f.get("id")] = nid
            bff.set("fontCnt", str(len(bff)))
        # 나머지 목록: 뒤에 붙이고 id 를 새로
        keys = dict(zip(self.LISTS, ["bf", "cp", "tab", "num", "pp"]))
        news = {}
        for name in self.LISTS:
            sl, bl = self._list(sh, name), self._list(self.head, name)
            if sl is None:
                continue
            if bl is None:
                bl = etree.SubElement(self.head.find(".//hh:refList", NS), "{%s}%s" % (NS["hh"], name))
            ids = [int(e.get("id")) for e in bl]
            nxt = (max(ids) + 1) if ids else (1 if name in ("borderFills", "numberings") else 0)
            for e in sl:
                ne = copy.deepcopy(e)
                m[keys[name]][e.get("id")] = str(nxt)
                ne.set("id", str(nxt)); nxt += 1
                bl.append(ne); news.setdefault(name, []).append(ne)
            bl.set("itemCnt", str(len(bl)))
        # 덧붙인 서식 안의 참조 번호 바꾸기
        LANG = {"hangul": "HANGUL", "latin": "LATIN", "hanja": "HANJA", "japanese": "JAPANESE",
                "other": "OTHER", "symbol": "SYMBOL", "user": "USER"}
        for cp in news.get("charProperties", []):
            fr = cp.find("hh:fontRef", NS)
            if fr is not None:
                for a, lang in LANG.items():
                    if fr.get(a) in m["font"].get(lang, {}):
                        fr.set(a, m["font"][lang][fr.get(a)])
            if cp.get("borderFillIDRef") in m["bf"]:
                cp.set("borderFillIDRef", m["bf"][cp.get("borderFillIDRef")])
        # xmlVersion 1.3(한글 2020 등) 파일은 문단 여백·탭 위치를 2배 값으로 적는다 → 1.5 문서에 넣을 땐 반으로
        ver = float(re.search(rb'xmlVersion="([\d.]+)"', src_zip.read("version.xml")).group(1))
        if ver < 1.5:
            for pp in news.get("paraProperties", []):
                for n in pp.iter():
                    if L(n) in ("intent", "left", "right", "prev", "next") and n.get("unit", "HWPUNIT") == "HWPUNIT":
                        n.set("value", str(int(n.get("value")) // 2))
            for tp in news.get("tabProperties", []):
                for n in tp.iter():
                    if L(n) == "tabItem":
                        n.set("pos", str(int(n.get("pos")) // 2))
        for pp in news.get("paraProperties", []):
            if pp.get("tabPrIDRef") in m["tab"]:
                pp.set("tabPrIDRef", m["tab"][pp.get("tabPrIDRef")])
            for n in pp.iter():
                if L(n) == "border" and n.get("borderFillIDRef") in m["bf"]:
                    n.set("borderFillIDRef", m["bf"][n.get("borderFillIDRef")])
                if L(n) == "heading" and n.get("type") in ("NUMBER", "BULLET") and n.get("idRef") in m["num"]:
                    n.set("idRef", m["num"][n.get("idRef")])
        m["zip"] = src_zip
        m["hpf"] = etree.fromstring(src_zip.read("Contents/content.hpf"))
        self.maps[key] = m
        return m

    def _bin(self, m, ref):
        if ref in m["bin"]:
            return m["bin"][ref]
        item = m["hpf"].find(".//opf:item[@id='%s']" % ref, NS)
        href = item.get("href")
        self.nbin += 1
        nid = "cp%04d" % self.nbin
        nhref = "BinData/%s%s" % (nid, os.path.splitext(href)[1])
        self.files[nhref] = m["zip"].read(href)
        man = self.hpf.find(".//opf:manifest", NS)
        ni = copy.deepcopy(item); ni.set("id", nid); ni.set("href", nhref)
        man.append(ni)
        m["bin"][ref] = nid
        return nid

    def import_paras(self, m, paras):
        out = []
        for p in paras:
            q = copy.deepcopy(p)
            for n in q.iter():
                for a, key in (("charPrIDRef", "cp"), ("paraPrIDRef", "pp"), ("borderFillIDRef", "bf")):
                    if n.get(a) is not None and n.get(a) in m[key]:
                        n.set(a, m[key][n.get(a)])
                if n.get("styleIDRef") is not None:
                    n.set("styleIDRef", "0")
                if n.get("binaryItemIDRef") is not None:
                    n.set("binaryItemIDRef", self._bin(m, n.get("binaryItemIDRef")))
            for o in q.iter(HP + "pic", HP + "container"):      # 글 옆 그림: 단 오른쪽 끝에, 글은 왼쪽으로만
                pos = o.find(HP + "pos")
                if o.get("textWrap") == "SQUARE" and pos is not None and pos.get("treatAsChar") == "0" \
                        and int(pos.get("horzOffset", "0")) > 5000:
                    o.set("textFlow", "LEFT_ONLY")
                    pos.set("horzRelTo", "COLUMN"); pos.set("horzAlign", "RIGHT"); pos.set("horzOffset", "0")
            for ls in list(q.iter(HP + "linesegarray")):
                ls.getparent().remove(ls)
            for n in q.iter():                     # 원본 쪽 나눔·단 나눔은 빼기
                if L(n) == "p":
                    n.set("pageBreak", "0"); n.set("columnBreak", "0")
            out.append(q)
        return out

    def keep_with_next(self, paras):
        """한 문제의 문단이 단·쪽 사이에서 갈라지지 않게: 마지막 문단 빼고 '다음 문단과 함께'."""
        pl = self._list(self.head, "paraProperties")
        for p in paras[:-1]:
            pid = p.get("paraPrIDRef")
            if pid not in self.keep:
                src = next(e for e in pl if e.get("id") == pid)
                ne = copy.deepcopy(src)
                ne.set("id", str(max(int(e.get("id")) for e in pl) + 1))
                bs = ne.find("hh:breakSetting", NS)
                if bs is not None:
                    bs.set("keepWithNext", "1")
                pl.append(ne); pl.set("itemCnt", str(len(pl)))
                self.keep[pid] = ne.get("id")
            p.set("paraPrIDRef", self.keep[pid])

    def save(self, path, paras):
        body = self.sec
        tops = [c for c in body if L(c) == "p"]
        for extra in tops[1:]:                     # 양식의 빈 문단 제거 (첫 구역 설정 문단만 남김)
            body.remove(extra)
        for p in paras:
            body.append(p)
        self.files["Contents/header.xml"] = etree.tostring(self.head, xml_declaration=True, encoding="UTF-8", standalone=True)
        self.files["Contents/section0.xml"] = etree.tostring(body, xml_declaration=True, encoding="UTF-8", standalone=True)
        self.files["Contents/content.hpf"] = etree.tostring(self.hpf, xml_declaration=True, encoding="UTF-8", standalone=True)
        with zipfile.ZipFile(path, "w") as dst:
            order = ["mimetype"] + [n for n in self.files if n != "mimetype"]
            for n in order:
                info = self.infos.get(n) or zipfile.ZipInfo(n)
                ct = zipfile.ZIP_STORED if n == "mimetype" else zipfile.ZIP_DEFLATED
                dst.writestr(info if n in self.infos else n, self.files[n], compress_type=ct)


def empty_para(ref):
    q = copy.deepcopy(ref)
    for c in list(q):
        q.remove(c)
    r = etree.SubElement(q, HP + "run"); r.set("charPrIDRef", "0")
    q.set("paraPrIDRef", "0"); q.set("styleIDRef", "0")
    return q


def main():
    cmd = sys.argv[1]
    if cmd == "list":
        z = zipfile.ZipFile(sys.argv[2])
        sec = etree.fromstring(z.read("Contents/section0.xml"))
        for i, (num, body) in enumerate(find_problems(sec)):
            print(i, num, len(body), para_text(body[0])[:70])
        return
    out = sys.argv[2]
    tmp = os.path.join(tempfile.mkdtemp(), os.path.basename(out))
    build_hwpx.build([], tmp)
    with open(tmp, "rb") as f:
        mg = Merger(f.read())
    paras = []
    for spec in sys.argv[3:]:
        path, idx = spec.rsplit(":", 1)
        z = zipfile.ZipFile(path)
        probs = find_problems(etree.fromstring(z.read("Contents/section0.xml")))
        m = mg.add_source(path, z)
        for i in map(int, idx.split(",")):
            ps = mg.import_paras(m, probs[i][1])
            mg.keep_with_next(ps)
            paras += ps + [empty_para(ps[0]), empty_para(ps[0])]
    mg.save(out, paras)
    print("저장:", out, len(paras), "문단")


if __name__ == "__main__":
    main()
