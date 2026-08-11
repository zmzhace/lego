import io, gzip
from lddstudio.rebrickable import parse_rebrickable_parts_csv

def test_parse_parts_csv():
    csv_data = b"part_num,name,part_cat_id,part_material\n3001,Brick 2 x 4,1,1\n3002,Brick 2 x 3,1,1\n"
    data = gzip.compress(csv_data)
    import os
    os.makedirs("tmp", exist_ok=True)
    open("tmp/parts.csv.gz", "wb").write(data)
    parts = parse_rebrickable_parts_csv("tmp/parts.csv.gz")
    assert parts["3001"] == "Brick 2 x 4"
    assert parts["3002"] == "Brick 2 x 3"
