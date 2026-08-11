from xml.dom import minidom
from typing import NamedTuple


class Bone:
    def __init__(self, ref_id, transformation):
        self.ref_id = ref_id
        try:
            self.transformation = [float(x) for x in transformation]
        except (TypeError, ValueError):
            self.transformation = [0.0] * 12

    def rotation3(self):
        t = self.transformation
        return ((t[0], t[1], t[2]), (t[3], t[4], t[5]), (t[6], t[7], t[8]))

    def translation(self):
        t = self.transformation
        return (t[9], t[10], t[11])


class Part:
    def __init__(self, ref_id, design_id, materials, decoration, bones):
        self.ref_id = ref_id
        self.design_id = design_id
        self.materials = materials
        self.decoration = decoration
        self.bones = bones


class Brick:
    def __init__(self, ref_id, design_id, parts):
        self.ref_id = ref_id
        self.design_id = design_id
        self.parts = parts


class Group:
    def __init__(self, part_refs):
        self.part_refs = part_refs


class LxfmlScene:
    def __init__(self, name, brick_version, bricks, groups, cameras=None, extra_xml=None):
        self.name = name
        self.brick_version = brick_version
        self.bricks = bricks
        self.groups = [g.part_refs for g in groups]
        self.cameras = cameras if cameras is not None else []
        self.extra_xml = extra_xml if extra_xml is not None else []


def _parse_part(node):
    bones = []
    for child in node.childNodes:
        if child.nodeName == "Bone":
            bones.append(Bone(child.getAttribute("refID"),
                              child.getAttribute("transformation").split(",")))
    deco = node.getAttribute("decoration") if node.hasAttribute("decoration") else None
    materials = [m for m in node.getAttribute("materials").split(",") if m != ""]
    return Part(node.getAttribute("refID"), node.getAttribute("designID"),
                materials, deco, bones)


def parse_lxfml(data: bytes) -> LxfmlScene:
    doc = minidom.parseString(data)
    root = doc.documentElement
    name = root.getAttribute("name")
    brick_version = ""
    bricks = []
    groups = []
    cameras = []
    extra_xml = []
    for node in root.childNodes:
        if node.nodeName == "Meta":
            for child in node.childNodes:
                if child.nodeName == "BrickSet":
                    brick_version = child.getAttribute("version")
        elif node.nodeName == "Bricks":
            for child in node.childNodes:
                if child.nodeName == "Brick":
                    parts = [_parse_part(p) for p in child.childNodes if p.nodeName == "Part"]
                    bricks.append(Brick(child.getAttribute("refID"),
                                        child.getAttribute("designID"), parts))
        elif node.nodeName == "GroupSystems":
            for gs in node.childNodes:
                if gs.nodeName == "GroupSystem":
                    for g in gs.childNodes:
                        if g.nodeName == "Group":
                            refs = g.getAttribute("partRefs").split(",")
                            if refs != [""]:
                                groups.append(Group(refs))
        elif node.nodeName == "Cameras":
            for cam in node.childNodes:
                if cam.nodeName == "Camera":
                    attrs = {}
                    if cam.attributes:
                        for a in cam.attributes.values():
                            attrs[a.name] = a.value
                    cameras.append(attrs)
        elif node.nodeType == node.ELEMENT_NODE:
            extra_xml.append(node.toxml())
    return LxfmlScene(name, brick_version, bricks, groups, cameras, extra_xml)


def serialize_lxfml(scene: LxfmlScene) -> bytes:
    lines = ['<LXFML name="{}">'.format(scene.name)]
    lines.append('<Meta><BrickSet version="{}"/></Meta>'.format(scene.brick_version))
    if scene.cameras:
        lines.append("<Cameras>")
        for cam in scene.cameras:
            attrs = " ".join('{}="{}"'.format(k, v) for k, v in cam.items())
            lines.append("<Camera {}/>".format(attrs))
        lines.append("</Cameras>")
    lines.append("<Bricks>")
    for b in scene.bricks:
        lines.append('<Brick refID="{}" designID="{}">'.format(b.ref_id, b.design_id))
        for p in b.parts:
            attrs = 'refID="{}" designID="{}" materials="{}"'.format(
                p.ref_id, p.design_id, ",".join(p.materials))
            if p.decoration:
                attrs += ' decoration="{}"'.format(p.decoration)
            lines.append("<Part {}>".format(attrs))
            for bone in p.bones:
                lines.append('<Bone refID="{}" transformation="{}"/>'.format(
                    bone.ref_id, ",".join(str(x) for x in bone.transformation)))
            lines.append("</Part>")
        lines.append("</Brick>")
    lines.append("</Bricks>")
    lines.append("<GroupSystems><GroupSystem>")
    for grp in scene.groups:
        lines.append('<Group partRefs="{}"/>'.format(",".join(grp)))
    lines.append("</GroupSystem></GroupSystems>")
    lines.extend(scene.extra_xml)
    lines.append("</LXFML>")
    return "".join(lines).encode("utf-8")
