import io, zipfile
from lddstudio.lxf_parser import open_lxf, extract_lxfml, save_lxf

def make_lxf(lxfml: bytes) -> str:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("IMAGE100.LXFML", lxfml)
        z.writestr("IMAGE100.REF", b"refdata")
        z.writestr("library/thumb.png", b"png")
    open("tmp_test.lxf", "wb").write(buf.getvalue())
    return "tmp_test.lxf"

def test_open_lxf_reads_all_members():
    p = open_lxf(make_lxf(b"<LXFML/>"))
    assert "IMAGE100.LXFML" in p.members
    assert "IMAGE100.REF" in p.members
    assert "library/thumb.png" in p.members

def test_extract_lxfml():
    p = open_lxf(make_lxf(b"<LXFML name='x'/>"))
    assert extract_lxfml(p.members) == b"<LXFML name='x'/>"

def test_save_lxf_roundtrip_preserves_extra_files():
    p = open_lxf(make_lxf(b"<LXFML/>"))
    out = "tmp_out.lxf"
    save_lxf(p, out, {"IMAGE100.LXFML": b"<LXFML name='fixed'/>"})
    p2 = open_lxf(out)
    assert p2.members["IMAGE100.REF"] == b"refdata"
    assert p2.members["library/thumb.png"] == b"png"
    assert p2.members["IMAGE100.LXFML"] == b"<LXFML name='fixed'/>"
