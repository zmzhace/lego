import os

from .lxf_parser import open_lxf, save_lxf, extract_lxfml
from .lxfml_model import parse_lxfml, serialize_lxfml
from .mapping import MappingDb, PartMapping
from .report import ConversionReport


def convert(input_path, output_path, mapping_db, ldd_db, color_proc, fixer,
            fix_transform=True, studio_ldraw_dir="") -> ConversionReport:
    report = ConversionReport()
    pkg = open_lxf(input_path)
    scene = parse_lxfml(extract_lxfml(pkg.members))

    for brick in scene.bricks:
        for part in brick.parts:
            original_design_id = part.design_id
            mapping = mapping_db.lookup(original_design_id)
            if mapping and mapping.bl_number:
                report.replaced.append((original_design_id, mapping.bl_number))
                if mapping.bl_number != original_design_id:
                    report.disambiguated.append(
                        (original_design_id, mapping.bl_number))
                part.design_id = mapping.bl_number
            else:
                report.unmatched.append(mapping or PartMapping(original_design_id, None, ldd_db.primitive_names.get(original_design_id, ""), "unmatched"))
            resolved = [color_proc.resolve(mat_id) for mat_id in part.materials]
            for res in resolved:
                if res.is_custom and res.bl_color_id not in report.custom_colors:
                    report.custom_colors[res.bl_color_id] = (res.name, res.r, res.g, res.b)
            part.materials = [res.bl_color_id for res in resolved]
            if fix_transform:
                part.bones = [fixer.fix(b, original_design_id) for b in part.bones]

    if studio_ldraw_dir:
        conn_dir = os.path.join(studio_ldraw_dir, "connectivity")
        col_dir = os.path.join(studio_ldraw_dir, "collider")
        if os.path.isdir(conn_dir) and os.path.isdir(col_dir):
            seen = set()
            for b in scene.bricks:
                for p in b.parts:
                    if p.design_id in seen:
                        continue
                    seen.add(p.design_id)
                    if not os.path.isfile(os.path.join(conn_dir, p.design_id + ".conn")) or \
                       not os.path.isfile(os.path.join(col_dir, p.design_id + ".col")):
                        report.missing_conn_collider.append(p.design_id)

    save_lxf(pkg, output_path, {"IMAGE100.LXFML": serialize_lxfml(scene)})
    return report
