import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lddstudio.studio_data import (load_studio_mapping, build_official_dat_index,
                                   disambiguate_candidates)
from lddstudio.ldd_db import load_ldd_database

STUDIO_DATA = os.environ.get("LDDSTUDIO_STUDIO_DATA_DIR",
                            "/var/folders/sn/hh7w4g_j2g738_qpyw313rch0000gp/T/opencode/lddstudio-install/payload/data")
LDD_DB = os.environ.get("LDDSTUDIO_LDD_DB",
                        "/var/folders/sn/hh7w4g_j2g738_qpyw313rch0000gp/T/opencode/lddstudio-install/db.lif")


def main():
    sd = STUDIO_DATA
    if not os.path.isfile(os.path.join(sd, "StudioPartDefinition2.txt")):
        print("Studio data not found:", sd)
        return 1
    ldd_to_bl, _offsets, filenames = load_studio_mapping(sd)
    # NOTE: filenames values are lists (Task 2 起，{did: [候选]}).
    # disambiguate_candidates 返回值是 {did: 单个 .dat 文件名}.
    ldraw_dir = os.path.join(os.path.dirname(sd), "ldraw")
    official = build_official_dat_index(ldraw_dir)
    dis = disambiguate_candidates(filenames, official)

    # 消歧真触发数：多候选且消歧后与无消歧基线（最后候选）不同
    n_dis = 0
    for did, f in dis.items():
        baseline = filenames[did][-1] if filenames.get(did) else ""
        if f != baseline:
            n_dis += 1

    # 未匹配：LDD palette 全集减去已映射
    unmatched = "n/a (no LDD db)"
    if os.path.isfile(LDD_DB):
        ldd_db = load_ldd_database(LDD_DB)
        unmatched = len([did for did in ldd_db.primitive_names
                         if did not in ldd_to_bl])

    bls = set(ldd_to_bl.values())
    # 缺 .conn 或 .col（双查）
    missing = [bl for bl in bls
               if bl and (
                   not os.path.isfile(os.path.join(ldraw_dir, "connectivity", bl + ".conn")) or
                   not os.path.isfile(os.path.join(ldraw_dir, "collider", bl + ".col")))]
    print("mapped total:", len(ldd_to_bl))
    print("disambiguated (true triggers):", n_dis)
    print("official .dat: {}/{} ({:.1f}%)".format(
        sum(1 for bl in bls if bl in official), len(bls),
        100.0 * sum(1 for bl in bls if bl in official) / len(bls) if bls else 0.0))
    print("unmatched (LDD palette):", unmatched)
    print("missing .conn or .col:", len(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
