"""Scan all real models for designIDs that Studio's libraries do NOT contain.
These are 'custom parts' the user cares about - can we generate .dat for them?"""
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lddstudio.lxf_parser import open_lxf, extract_lxfml
from lddstudio.lxfml_model import parse_lxfml

# All Studio ldraw part filenames (any dir)
ldraw_files = set()
for root, _, files in os.walk(r"D:\Studio 2.0\ldraw"):
    for f in files:
        if f.endswith(".dat"):
            ldraw_files.add(os.path.splitext(f)[0])
# All BL/studio numbers in partdef
partdef_ids = set()
rows = open(r"D:\Studio 2.0\data\StudioPartDefinition2.txt", encoding="utf-8").read().splitlines()
for r in rows[1:]:
    c = r.split("\t")
    for i in (0, 1, 2, 4):
        if i < len(c) and c[i].strip():
            partdef_ids.add(c[i].strip())
# all ldraw.xml mapping ldraw numbers
import re
for fn in ("ldraw_new.xml", "ldraw_lxfv56.xml"):
    data = open(os.path.join(r"D:\Studio 2.0\data", fn), encoding="utf-8", errors="replace").read()
    for m in re.finditer(r'(?:ldraw|filename)="([^"]+\.dat)"', data):
        partdef_ids.add(os.path.splitext(m.group(1))[0])

known = ldraw_files | partdef_ids

models = glob.glob(os.path.join(r"D:\lego\tests\fixtures\models", "*.lxf"))
for lxf in sorted(models):
    scene = parse_lxfml(extract_lxfml(open_lxf(lxf).members))
    seen = {}
    for b in scene.bricks:
        for p in b.parts:
            seen.setdefault(p.design_id, 0)
            seen[p.design_id] += 1
    unknown = {d: c for d, c in seen.items()
               if d not in known and not d.startswith("bl_")}
    if unknown:
        print("{}: {} unknown part ids".format(os.path.basename(lxf), len(unknown)))
        for d, c in sorted(unknown.items()):
            print("    {} (x{})".format(d, c))
print("\n(total known Studio ids: {})".format(len(known)))
