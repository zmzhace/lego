import argparse
import os
import sys

from .mapping import MappingDb, default_db_path
from .ldd_db import find_ldd_db, load_ldd_database, LddDatabase
from .colors import ColorProcessor, load_bl_color_map
from .transform import TransformFixer
from .converter import convert
from .resources import data_dir
from .studio_lib import find_studio_dir, scan_studio_part_numbers


def build_mapping_db(db_path, ldd_db, rebrickable_csv=None, studio_numbers=None,
                     force_rebuild=False):
    db = MappingDb(db_path)
    bl_parts = {}
    bl_numbers = set()
    if rebrickable_csv and os.path.exists(rebrickable_csv):
        from .rebrickable import parse_rebrickable_parts_csv
        bl_parts = parse_rebrickable_parts_csv(rebrickable_csv)
        bl_numbers = set(bl_parts.keys())
    if studio_numbers:
        bl_numbers |= set(studio_numbers)
    if force_rebuild or db.is_empty():
        db.rebuild(ldd_db.primitive_names, bl_parts, bl_numbers)
    return db


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="lddstudio")
    sub = parser.add_subparsers(dest="cmd")
    conv = sub.add_parser("convert")
    conv.add_argument("input")
    conv.add_argument("output")
    conv.add_argument("--mapping")
    conv.add_argument("--rebrickable")
    conv.add_argument("--rebuild-mapping", action="store_true")
    conv.add_argument("--ldd-db")
    conv.add_argument("--no-fix-transform", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "convert":
        ldd_path = args.ldd_db or find_ldd_db()
        ldd_db = load_ldd_database(ldd_path) if ldd_path else LddDatabase({}, {}, {}, {})
        db_path = args.mapping or default_db_path()
        db = build_mapping_db(db_path, ldd_db, args.rebrickable,
                              studio_numbers=scan_studio_part_numbers(find_studio_dir()),
                              force_rebuild=args.rebuild_mapping)
        bl_map = load_bl_color_map(os.path.join(data_dir(), "ldd_to_bl_colors.csv"))
        cp = ColorProcessor(bl_map, {}, ldd_db.materials)
        fixer = TransformFixer(ldd_db.geo_bounding, {})
        rep = convert(args.input, args.output, db, ldd_db, cp, fixer,
                      fix_transform=not args.no_fix_transform)
        print("替换 {} 条，未匹配 {} 条，自定义色 {} 条".format(
            len(rep.replaced), len(rep.unmatched), len(rep.custom_colors)))
        for m in rep.unmatched:
            print("  未匹配: {}".format(m.design_id))
        return 0
    parser.print_help()
    return 1
