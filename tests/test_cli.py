import os
from lddstudio.cli import main


def test_cli_convert_minimal(tmp_path, monkeypatch):
    import io, zipfile
    lxfml = b'<LXFML name="t"><Bricks></Bricks></LXFML>'
    inp = str(tmp_path / "in.lxf")
    out = str(tmp_path / "out.lxf")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("IMAGE100.LXFML", lxfml)
    open(inp, "wb").write(buf.getvalue())
    rc = main(["convert", inp, out, "--no-fix-transform"])
    assert rc == 0
    assert os.path.exists(out)
