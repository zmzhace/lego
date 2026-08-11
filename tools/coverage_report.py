import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lddstudio.cli import build_mapping_db, find_studio_data_dir
from lddstudio.ldd_db import LIFReader, LddDatabase
from lddstudio.mapping import MappingDb
from lddstudio.studio_lib import scan_studio_part_numbers

DATA = r"D:\Studio 2.0\data"
STUDIO_DIR = r"D:\Studio 2.0"

pal = os.path.join(os.environ.get("APPDATA", ""), "LEGO Company",
                   "LEGO Digital Designer", "Palettes", "LDD.lif")
r = LIFReader(pal)
xml = r.filelist["/LDD.paxml"].read().decode("utf-8", errors="replace")
ids = set(re.findall(r'designID="(\d+)"', xml))
print("LDD palette part count:", len(ids))

# build mapping db with studio dir (both authoritative seed + identity fallback)
db_path = "tmp_e2e/map.db"
if os.path.exists(db_path):
    os.remove(db_path)
ldd_db = LddDatabase({}, {i: "p" for i in ids}, {}, {})
db = build_mapping_db(db_path, ldd_db,
                      studio_numbers=scan_studio_part_numbers(STUDIO_DIR),
                      studio_data_dir=DATA)

mapped = {i for i in ids if db.lookup(i) and db.lookup(i).bl_number}
print("mapped:", len(mapped), "/", len(ids), "({:.1f}%)".format(100.0 * len(mapped) / len(ids)))
unmapped = sorted(ids - mapped)
print("unmapped:", unmapped)

# report by match type
from collections import Counter
types = Counter(db.lookup(i).match_type for i in ids)
print("match types:", dict(types))
db.close()
