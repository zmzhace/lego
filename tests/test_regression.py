import io
import os
import zipfile

from tools.regression import count_parts, run
from lddstudio.mapping import MappingDb

LXFML = b'''<LXFML name="reg"><Bricks>
<Brick refID="1" designID="3001"><Part refID="2" designID="3001" materials="5">
<Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/></Part></Brick>
<Brick refID="3" designID="99999"><Part refID="4" designID="99999" materials="77">
<Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/></Part></Brick>
</Bricks></LXFML>'''


def _make_lxf(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("IMAGE100.LXFML", LXFML)
    open(path, "wb").write(buf.getvalue())


def test_count_parts_synthetic(tmp_path):
    path = str(tmp_path / "a.lxf")
    _make_lxf(path)
    assert count_parts(path) == 2


def test_run_end_to_end_synthetic(tmp_path):
    inp = tmp_path / "in"
    inp.mkdir()
    _make_lxf(str(inp / "a.lxf"))
    out = tmp_path / "out"
    db = MappingDb(str(tmp_path / "map.db"))
    db.set_manual("3001", "3001")
    results = run(str(inp), str(out), str(tmp_path / "map.db"))
    assert len(results) == 1
    r = results[0]
    assert r["parts_before"] == 2
    assert r["parts_after"] == 2
    assert r["count_ok"] is True
    assert r["no_silent"] is True
    assert r["replaced"] == 1
    assert "99999" in r["unmatched"]
    out_lxf = str(out / "a.lxf")
    assert os.path.exists(out_lxf)
    assert count_parts(out_lxf) == 2
