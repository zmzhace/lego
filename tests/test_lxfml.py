from lddstudio.lxfml_model import parse_lxfml, serialize_lxfml

LXFML = b'''<LXFML name="test">
<Meta><BrickSet version="1"/></Meta>
<Bricks>
  <Brick refID="1" designID="3001">
    <Part refID="2" designID="3001" materials="5,0,4">
      <Bone refID="0" transformation="1,0,0,0,1,0,0,0,1,0,0,0"/>
    </Part>
  </Brick>
</Bricks>
<GroupSystems><GroupSystem><Group partRefs="2,9"/></GroupSystem></GroupSystems>
</LXFML>'''

def test_parse_bricks_and_parts():
    s = parse_lxfml(LXFML)
    assert s.name == "test"
    assert len(s.bricks) == 1
    brick = s.bricks[0]
    assert brick.design_id == "3001"
    assert len(brick.parts) == 1
    part = brick.parts[0]
    assert part.materials == ["5", "0", "4"]
    assert part.bones[0].transformation[0] == 1.0

def test_parse_groups():
    s = parse_lxfml(LXFML)
    assert s.groups == [["2", "9"]]

def test_serialize_roundtrip():
    s = parse_lxfml(LXFML)
    out = serialize_lxfml(s)
    s2 = parse_lxfml(out)
    assert s2.bricks[0].parts[0].materials == ["5", "0", "4"]
    assert s2.groups == [["2", "9"]]
