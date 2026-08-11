import os
from lddstudio.studio_lib import scan_studio_part_numbers

def test_scan_studio_part_numbers_collects_bl_ids():
    os.makedirs("tmp_studio/parts", exist_ok=True)
    open("tmp_studio/parts/3001.dat", "w").write("")
    open("tmp_studio/parts/3002.io", "w").write("")
    open("tmp_studio/readme.txt", "w").write("")
    ids = scan_studio_part_numbers("tmp_studio")
    assert "3001" in ids and "3002" in ids
