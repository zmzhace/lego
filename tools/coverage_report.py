import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from lddstudio.studio_data import (load_studio_mapping, build_official_dat_index,
                                   disambiguate_candidates)

STUDIO_DATA = os.environ.get("LDDSTUDIO_STUDIO_DATA_DIR",
                            "/var/folders/sn/hh7w4g_j2g738_qpyw313rch0000gp/T/opencode/lddstudio-install/payload/data")


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

    # 消歧 = 多候选且映射后编号与无消歧基线不同
    n_dis = 0
    for did, f in dis.items():
        bl = ldd_to_bl.get(did)
        base = f[:-4] if f.endswith(".dat") else f
        if bl and bl != base and did != bl:
            n_dis += 1
    missing_conn = [bl for bl in set(ldd_to_bl.values())
                    if bl and not os.path.isfile(
                        os.path.join(ldraw_dir, "connectivity", bl + ".conn"))]
    print("mapped total:", len(ldd_to_bl))
    print("disambiguated:", n_dis)
    print("official .dat:", sum(1 for bl in set(ldd_to_bl.values())
                                if bl in official))
    print("missing conn/col for mapped:", len(missing_conn))
    return 0


if __name__ == "__main__":
    sys.exit(main())
