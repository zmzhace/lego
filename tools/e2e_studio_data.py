import os
import sys
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lddstudio.cli import build_mapping_db, find_studio_data_dir
from lddstudio.ldd_db import LddDatabase
from lddstudio.colors import ColorProcessor, load_bl_color_map
from lddstudio.transform import TransformFixer
from lddstudio.converter import convert
from lddstudio.resources import data_dir
from lddstudio.studio_data import (load_color_definition, load_studio_mapping,
                                   studio_colors_for_ldd)

STUDIO_DIR = r"D:\Studio 2.0"
DATA_DIR = os.path.join(STUDIO_DIR, "data")

parts = []
parts.append('<Brick refID="1" designID="3001"><Part refID="2" designID="3001" materials="5">'
             '<Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/></Part></Brick>')
parts.append('<Brick refID="3" designID="44740"><Part refID="4" designID="44740" materials="23">'
             '<Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,10,20,30"/></Part></Brick>')
parts.append('<Brick refID="5" designID="41823"><Part refID="6" designID="41823" materials="26">'
             '<Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/></Part></Brick>')
parts.append('<Brick refID="7" designID="99999"><Part refID="8" designID="99999" materials="77">'
             '<Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,5,6,7"/></Part></Brick>')

lxfml = ('<LXFML name="e2e"><Bricks>' + "".join(parts) + '</Bricks></LXFML>').encode()

os.makedirs("tmp_e2e", exist_ok=True)
inp = "tmp_e2e/in.lxf"
with zipfile.ZipFile(inp, "w") as z:
    z.writestr("IMAGE100.LXFML", lxfml)

ldd_db = LddDatabase({}, {"3001": "Brick 2 x 4", "44740": "Bracket", "41823": "Antenna",
                          "99999": "Unknown"}, {}, {})
db_path = "tmp_e2e/map.db"
if os.path.exists(db_path):
    os.remove(db_path)
db = build_mapping_db(db_path, ldd_db, studio_data_dir=DATA_DIR)

for pid in ("3001", "44740", "41823", "99999"):
    print("mapping", pid, "->", db.lookup(pid))

studio_colors = studio_colors_for_ldd(load_color_definition(DATA_DIR))
bl_map = load_bl_color_map(os.path.join(data_dir(), "ldd_to_bl_colors.csv"))
cp = ColorProcessor(bl_map, studio_colors, ldd_db.materials, studio_color_map=studio_colors)

_ldd_to_bl, offsets, _f = load_studio_mapping(DATA_DIR)
fixer = TransformFixer(ldd_db.geo_bounding, {}, offsets)

rep = convert(inp, "tmp_e2e/out.lxf", db, ldd_db, cp, fixer, fix_transform=True)
print("\nreplaced:", rep.replaced)
print("unmatched:", [m.design_id for m in rep.unmatched])
print("custom colors:", rep.custom_colors)

with zipfile.ZipFile("tmp_e2e/out.lxf") as z:
    out_xml = z.read("IMAGE100.LXFML").decode()

print("\n--- output XML ---")
print(out_xml)

assert 'designID="3001"' in out_xml
assert 'materials="2"' in out_xml          # LDD material 5 -> Studio color 2
assert 'designID="44740"' in out_xml
assert 'designID="41823"' in out_xml
assert 'designID="99999"' in out_xml       # unmatched preserved
assert 'materials="C77"' in out_xml        # custom color written
print("\nOK")
