import os, io, zipfile
from lddstudio.converter import convert
from lddstudio.report import ConversionReport
from lddstudio.mapping import MappingDb
from lddstudio.ldd_db import LddDatabase, MaterialDef
from lddstudio.colors import ColorProcessor
from lddstudio.transform import TransformFixer
from lddstudio.studio_data import TransformOffset

def make_input(lxfml: bytes) -> str:
    os.makedirs("tmp", exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("IMAGE100.LXFML", lxfml)
    open("tmp/in.lxf", "wb").write(buf.getvalue())
    return "tmp/in.lxf"

LXF = b'''<LXFML name="t"><Bricks>
<Brick refID="1" designID="3001"><Part refID="2" designID="3001" materials="5">
<Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/></Part></Brick>
<Brick refID="3" designID="99999"><Part refID="4" designID="99999" materials="77">
<Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/></Part></Brick>
</Bricks></LXFML>'''

def setup():
    db = MappingDb("tmp/conv_map.db")
    db.rebuild({"3001": "Brick 2 x 4", "99999": "Unknown"}, {"3001": "Brick 2 x 4"}, {"3001"})
    return db

def test_convert_replaces_mapped_and_reports_unmatched():
    make_input(LXF)
    db = setup()
    ldd_db = LddDatabase({}, {"3001": "Brick 2 x 4", "99999": "Unknown"}, {}, {})
    cp = ColorProcessor({"5": ("5", 196, 0, 38, "Solid")}, {}, {})
    fixer = TransformFixer({}, {})
    rep = convert("tmp/in.lxf", "tmp/out.lxf", db, ldd_db, cp, fixer, fix_transform=False)
    assert len(rep.unmatched) == 1
    assert rep.unmatched[0].design_id == "99999"
    # 输出文件包含替换后的 3001 且保留 materials
    import zipfile
    with zipfile.ZipFile("tmp/out.lxf") as z:
        data = z.read("IMAGE100.LXFML").decode()
    assert 'designID="3001"' in data
    assert 'materials="5"' in data
    assert 'designID="99999"' in data  # 未匹配保底不替换


def test_convert_writes_resolved_bl_color_id():
    make_input(b'''<LXFML name="t"><Bricks>
    <Brick refID="1" designID="3001"><Part refID="2" designID="3001" materials="5">
    <Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/></Part></Brick>
    </Bricks></LXFML>''')
    db = setup()
    ldd_db = LddDatabase({}, {"3001": "Brick 2 x 4"}, {}, {})
    cp = ColorProcessor({"5": ("2", 196, 0, 38, "Solid")}, {}, {})
    fixer = TransformFixer({}, {})
    rep = convert("tmp/in.lxf", "tmp/out.lxf", db, ldd_db, cp, fixer, fix_transform=False)
    assert rep.custom_colors == {}
    with zipfile.ZipFile("tmp/out.lxf") as z:
        data = z.read("IMAGE100.LXFML").decode()
    assert 'materials="2"' in data
    assert 'materials="5"' not in data


def test_convert_writes_custom_color_id_and_reports():
    make_input(b'''<LXFML name="t"><Bricks>
    <Brick refID="1" designID="3001"><Part refID="2" designID="3001" materials="77">
    <Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/></Part></Brick>
    </Bricks></LXFML>''')
    db = setup()
    ldd_db = LddDatabase({}, {"3001": "Brick 2 x 4"}, {}, {})
    cp = ColorProcessor({}, {}, {})
    fixer = TransformFixer({}, {})
    rep = convert("tmp/in.lxf", "tmp/out.lxf", db, ldd_db, cp, fixer, fix_transform=False)
    assert len(rep.custom_colors) == 1
    cid = next(iter(rep.custom_colors))
    assert cid.isdigit()
    with zipfile.ZipFile("tmp/out.lxf") as z:
        data = z.read("IMAGE100.LXFML").decode()
    assert 'materials="{}"'.format(cid) in data


def test_convert_applies_offset_by_original_ldd_id():
    make_input(b'''<LXFML name="t"><Bricks>
    <Brick refID="1" designID="6014"><Part refID="2" designID="6014" materials="23">
    <Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/></Part></Brick>
    </Bricks></LXFML>''')
    db = MappingDb("tmp/conv_map2.db")
    db.seed_from_studio({"6014": "6014a"})
    db.close()
    db = MappingDb("tmp/conv_map2.db")
    ldd_db = LddDatabase({}, {"6014": "Wheel"}, {}, {})
    cp = ColorProcessor({}, {}, {})
    off = TransformOffset(0, 180, 0, 0, -0.25, -7.75)
    fixer = TransformFixer({}, {}, {"6014": off})
    rep = convert("tmp/in.lxf", "tmp/out.lxf", db, ldd_db, cp, fixer, fix_transform=True)
    assert rep.replaced == [("6014", "6014a")]
    assert rep.disambiguated == [("6014", "6014a")]
    assert rep.missing_conn_collider == []
    with zipfile.ZipFile("tmp/out.lxf") as z:
        data = z.read("IMAGE100.LXFML").decode()
    assert 'designID="6014a"' in data
    # 偏移应应用到骨骼变换（旋转 180 度 + 平移）
    assert '-7.75' in data
    db.close()


def test_report_disambiguated_and_missing_conn():
    rep = ConversionReport()
    rep.disambiguated.append(("76257", "22463"))
    rep.missing_conn_collider.append("99999")
    html = rep.to_html()
    assert "76257" in html and "22463" in html
    assert "99999" in html
