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
from .studio_data import (build_ldd_color_map, build_ldd_to_bl_map,
                          load_color_definition, load_studio_mapping,
                          load_transform_offsets, studio_colors_for_ldd)


def find_studio_data_dir() -> str:
    studio_dir = find_studio_dir()
    if not studio_dir:
        return ""
    for sub in ("data", "Studio_Data/data"):
        p = os.path.join(studio_dir, sub)
        if os.path.isdir(p):
            return p
    return studio_dir


def build_mapping_db(db_path, ldd_db, rebrickable_csv=None, studio_numbers=None,
                     force_rebuild=False, studio_data_dir=""):
    db = MappingDb(db_path)
    bl_parts = {}
    bl_numbers = set()
    if rebrickable_csv and os.path.exists(rebrickable_csv):
        from .rebrickable import parse_rebrickable_parts_csv
        bl_parts = parse_rebrickable_parts_csv(rebrickable_csv)
        bl_numbers = set(bl_parts.keys())
    if studio_numbers:
        bl_numbers |= set(studio_numbers)
    # Authoritative seed from Studio's own data files.
    if studio_data_dir:
        ldd_to_bl, offsets, _filenames = load_studio_mapping(studio_data_dir)
        if force_rebuild or db.is_empty():
            db.seed_from_studio(ldd_to_bl, names=ldd_db.primitive_names,
                                force=force_rebuild)
    if force_rebuild or db.is_empty():
        # Fuzzy-rebuild only the parts Studio does not know (keeps exact rows).
        db.fill_fuzzy_gaps(ldd_db.primitive_names, bl_parts, bl_numbers)
    else:
        # Fill identity gaps: LDD ids not yet mapped but present in the
        # Studio library as same-numbered parts (e.g. 59489.dat).
        for design_id in ldd_db.primitive_names:
            if db.lookup(design_id):
                continue
            if design_id in bl_numbers:
                db.conn.execute(
                    "INSERT OR REPLACE INTO parts VALUES (?,?,?,?)",
                    (design_id, design_id,
                     ldd_db.primitive_names.get(design_id, ""), "exact"))
        db.conn.commit()
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
    conv.add_argument("--studio-dir")
    conv.add_argument("--no-fix-transform", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "convert":
        ldd_path = args.ldd_db or find_ldd_db()
        ldd_db = load_ldd_database(ldd_path) if ldd_path else LddDatabase({}, {}, {}, {})
        db_path = args.mapping or default_db_path()
        studio_dir = args.studio_dir or find_studio_dir()
        studio_data_dir = find_studio_data_dir()
        db = build_mapping_db(db_path, ldd_db, args.rebrickable,
                              studio_numbers=scan_studio_part_numbers(studio_dir),
                              force_rebuild=args.rebuild_mapping,
                              studio_data_dir=studio_data_dir)
        bl_map = load_bl_color_map(os.path.join(data_dir(), "ldd_to_bl_colors.csv"))
        studio_colors = studio_colors_for_ldd(
            load_color_definition(studio_data_dir)) if studio_data_dir else {}
        cp = ColorProcessor(bl_map, studio_colors, ldd_db.materials,
                            studio_color_map=studio_colors)
        offsets = load_transform_offsets(studio_data_dir) if studio_data_dir else {}
        fixer = TransformFixer(ldd_db.geo_bounding, {}, offsets)
        ldraw_dir = os.path.join(os.path.dirname(studio_data_dir), "ldraw") \
            if studio_data_dir else ""
        rep = convert(args.input, args.output, db, ldd_db, cp, fixer,
                      fix_transform=not args.no_fix_transform,
                      studio_ldraw_dir=ldraw_dir)
        print("替换 {} 条，消歧 {} 条，未匹配 {} 条，自定义色 {} 条，缺连接点/碰撞 {} 条".format(
            len(rep.replaced), len(rep.disambiguated), len(rep.unmatched),
            len(rep.custom_colors), len(rep.missing_conn_collider)))
        for a, b in rep.disambiguated:
            print("  消歧: {} -> {}".format(a, b))
        for m in rep.unmatched:
            print("  未匹配: {}".format(m.design_id))
        for i in rep.missing_conn_collider:
            print("  缺连接点/碰撞体积: {}".format(i))
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
