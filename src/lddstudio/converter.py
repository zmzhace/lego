from .lxf_parser import open_lxf, save_lxf, extract_lxfml
from .lxfml_model import parse_lxfml, serialize_lxfml
from .mapping import MappingDb, PartMapping
from .report import ConversionReport


def convert(input_path, output_path, mapping_db, ldd_db, color_proc, fixer,
            fix_transform=True) -> ConversionReport:
    report = ConversionReport()
    pkg = open_lxf(input_path)
    scene = parse_lxfml(extract_lxfml(pkg.members))

    for brick in scene.bricks:
        for part in brick.parts:
            mapping = mapping_db.lookup(part.design_id)
            if mapping and mapping.bl_number:
                report.replaced.append((part.design_id, mapping.bl_number))
                part.design_id = mapping.bl_number
            else:
                report.unmatched.append(mapping or PartMapping(part.design_id, None, ldd_db.primitive_names.get(part.design_id, ""), "unmatched"))
            for mat_id in part.materials:
                res = color_proc.resolve(mat_id)
                if res.is_custom and res.bl_color_id not in report.custom_colors:
                    report.custom_colors[res.bl_color_id] = (res.name, res.r, res.g, res.b)
            if fix_transform:
                part.bones = [fixer.fix(b, part.design_id) for b in part.bones]

    save_lxf(pkg, output_path, {"IMAGE100.LXFML": serialize_lxfml(scene)})
    return report
