# poppler 로 다시 그린 쪽 이미지로 같은 크기의 PDF 를 만든다 (MuPDF 가 글자 일부를 못 그리는 원본 대책, 좌표 동일)
import fitz, glob, os, subprocess
S = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(S, "hwt_src.pdf")
od = os.path.join(S, "hwt_pop200")
os.makedirs(od, exist_ok=True)
subprocess.run(["pdftoppm", "-cropbox", "-r", "200", "-gray", "-png", src, os.path.join(od, "p")], check=True)
d = fitz.open(src)
out = fitz.open()
for i, pg in enumerate(d):
    f = glob.glob(os.path.join(od, f"p-{i+1:03d}.png"))[0]
    r = pg.rect
    np_ = out.new_page(width=r.width, height=r.height)
    np_.insert_image(np_.rect, filename=f)
    if pg.rotation:
        print("rotation!", i + 1, pg.rotation)
    if pg.cropbox != pg.mediabox:
        print("cropbox", i + 1, pg.cropbox, pg.mediabox)
out.save(os.path.join(S, "hwt_repaired.pdf"), deflate=True)
print("ok", len(out))
