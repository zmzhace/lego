import gzip
import os
import csv
import urllib.request

PARTS_CSV_URL = "https://rebrickable.com/media/downloads/parts.csv.gz"


def rebrickable_parts_csv_url() -> str:
    return PARTS_CSV_URL


def download_rebrickable_parts(out_path: str) -> None:
    urllib.request.urlretrieve(PARTS_CSV_URL, out_path)


def parse_rebrickable_parts_csv(path: str) -> dict:
    parts = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        header = next(reader)
        idx_num = header.index("part_num")
        idx_name = header.index("name")
        for row in reader:
            if len(row) <= max(idx_num, idx_name):
                continue
            parts[row[idx_num]] = row[idx_name]
    return parts
