import os
import sys

from lddstudio import resources


def test_data_dir_uses_meipass_when_bundled(tmp_path, monkeypatch):
    meipass = tmp_path / "_MEIPASS"
    (meipass / "data").mkdir(parents=True)
    monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    assert resources.data_dir() == os.path.join(str(meipass), "data")


def test_data_dir_dev_points_at_repo_data(tmp_path, monkeypatch):
    monkeypatch.delattr(sys, "_MEIPASS", raising=False)
    d = resources.data_dir()
    assert os.path.isdir(d)
    assert os.path.exists(os.path.join(d, "ldd_to_bl_colors.csv"))
