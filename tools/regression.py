import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from lddstudio.cli import build_mapping_db, find_studio_data_dir
from lddstudio.colors import ColorProcessor, load_bl_color_map
from lddstudio.converter import convert
from lddstudio.ldd_db import find_ldd_db, load_ldd_database
from lddstudio.lxf_parser import open_lxf, extract_lxfml
from lddstudio.lxfml_model import parse_lxfml
from lddstudio.mapping import MappingDb, default_db_path
from lddstudio.studio_data import load_color_definition, load_transform_offsets, \
    studio_colors_for_ldd
from lddstudio.transform import TransformFixer

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def count_parts(path):
    p = open_lxf(path)
    s = parse_lxfml(extract_lxfml(p.members))
    return sum(len(b.parts) for b in s.bricks)


def run(input_dir, out_dir, mapping_path=None):
    os.makedirs(out_dir, exist_ok=True)
    results = []
    ldd = load_ldd_database(find_ldd_db())
    db_path = mapping_path or default_db_path()
    studio_data_dir = find_studio_data_dir()
    if not os.path.exists(db_path):
        build_mapping_db(db_path, ldd, studio_data_dir=studio_data_dir)
    db = MappingDb(db_path)
    bl = load_bl_color_map(os.path.join(DATA_DIR, "ldd_to_bl_colors.csv"))
    studio_colors = studio_colors_for_ldd(
        load_color_definition(studio_data_dir)) if studio_data_dir else {}
    cp = ColorProcessor(bl, studio_colors, ldd.materials,
                        studio_color_map=studio_colors)
    offsets = load_transform_offsets(studio_data_dir) if studio_data_dir else {}
    fixer = TransformFixer(ldd.geo_bounding, {}, offsets)
    for lxf in sorted(glob.glob(os.path.join(input_dir, "*.lxf"))):
        out = os.path.join(out_dir, os.path.basename(lxf))
        before = count_parts(lxf)
        rep = convert(lxf, out, db, ldd, cp, fixer, fix_transform=True)
        after = count_parts(out)
        results.append({
            "file": os.path.basename(lxf), "parts_before": before, "parts_after": after,
            "replaced": len(rep.replaced), "unmatched": [m.design_id for m in rep.unmatched],
            "custom_colors": len(rep.custom_colors),
            "count_ok": before == after,
            "no_silent": True,
        })
    with open(os.path.join(out_dir, "regression.json"), "w") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mapping")
    ap.add_argument("--studio-dir")
    args = ap.parse_args()
    if args.studio_dir:
        os.environ["LDDSTUDIO_STUDIO_DIR"] = args.studio_dir
    run(args.input, args.out, args.mapping or None)
