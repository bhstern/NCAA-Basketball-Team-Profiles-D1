"""
Stitch per-year stage files back into the legacy combined layout (validation only).
----------------------------------------------------------------------------------
Works on the CSV TEXT, never through a DataFrame, so stitching cannot re-format a
single value: the stitched file is byte-comparable with what the original all-years
script writes.

    "concat"    -> seasons in year order (the original looped/concatenated by year)
    "sort:team" -> all rows re-sorted on the Team_Year key (the original sorted all years)

Output goes to <out_root>/stitched/ under the legacy file name.

Usage:
    python -m pipeline.dev.stitch --chain team                (all frozen seasons)
    python -m pipeline.dev.stitch --dataset master_team --year 2018 --year 2023
"""

import argparse
import csv
from pathlib import Path

from pipeline import config, guard
from pipeline.paths import DATASETS, PLAYER_DATASETS, TEAM_DATASETS, Paths

BOM = b"\xef\xbb\xbf"
CHAINS = {"team": TEAM_DATASETS, "player": PLAYER_DATASETS}


def parse_line(line):
    return next(csv.reader([line]))


class CsvText:
    """A CSV file held as raw lines: BOM flag, header line, data lines.

    Lines are kept exactly as written (quotes and all) so they can be compared and
    re-emitted byte-for-byte; fields are only parsed when a column is needed."""

    def __init__(self, path):
        self.path = Path(path)
        raw = self.path.read_bytes()
        self.bom = raw.startswith(BOM)
        text = raw[len(BOM):].decode("utf-8") if self.bom else raw.decode("utf-8")
        del raw
        if "\r" in text:
            raise ValueError(f"{self.path}: unexpected carriage returns (not written on this machine?)")
        if not text.endswith("\n"):
            raise ValueError(f"{self.path}: no trailing newline")
        lines = text[:-1].split("\n")
        del text
        self.header = lines[0]
        self.rows = lines[1:]
        self.fields = parse_line(self.header)

    def column(self, name):
        """One column's values. Also proves every line is exactly one well-formed record
        (a quoted field containing a newline would break line-based handling)."""
        i = self.fields.index(name)
        width = len(self.fields)
        values = []
        for record in csv.reader(self.rows):
            if len(record) != width:
                raise ValueError(f"{self.path}: data row {len(values)} has {len(record)} fields, "
                                 f"expected {width} (embedded newline or ragged row)")
            values.append(record[i])
        if len(values) != len(self.rows):
            raise ValueError(f"{self.path}: {len(self.rows)} lines parsed into {len(values)} records")
        return values

    def row_years(self, dataset):
        """Season of every data row, per the dataset's `year_from` rule."""
        if dataset.year_from == "team_suffix":
            return [int(t.rsplit("_", 1)[1]) for t in self.column("team")]
        return [int(float(y)) for y in self.column(dataset.year_from)]

    def rows_by_year(self, dataset):
        """{season: [raw lines]} with each season's lines in file order."""
        out = {}
        for line, year in zip(self.rows, self.row_years(dataset)):
            out.setdefault(year, []).append(line)
        return out


def to_bytes(bom, header, rows):
    return (BOM if bom else b"") + ("\n".join([header] + rows) + "\n").encode("utf-8")


def stitch(key, years, paths, source=None):
    """`source(year) -> Paths` says where each season's file lives (default: `paths`);
    the stitched file is always written under `paths`."""
    source = source or (lambda year: paths)
    dataset = DATASETS[key]
    parts = [CsvText(source(y).stage_file(key, y)) for y in sorted(years)]

    first = parts[0]
    for p in parts[1:]:
        if p.header != first.header:
            raise ValueError(f"{key}: header differs between {first.path} and {p.path}")
        if p.bom != first.bom:
            raise ValueError(f"{key}: BOM differs between {first.path} and {p.path}")

    for p in parts:
        p.row_years(dataset)   # validates every line is one well-formed record

    rows = [r for p in parts for r in p.rows]
    if dataset.stitch == "sort:team":
        i = first.fields.index("team")
        rows.sort(key=lambda r: parse_line(r)[i])
    elif dataset.stitch != "concat":
        raise ValueError(f"{key}: unknown stitch rule {dataset.stitch!r}")

    out = guard.write_bytes(paths.stitched_file(key), to_bytes(first.bom, first.header, rows), season=None)
    print(f"  stitched {key}: {len(parts)} season(s), {len(rows)} rows -> {out}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chain", choices=sorted(CHAINS))
    ap.add_argument("--dataset", action="append", choices=sorted(DATASETS))
    ap.add_argument("--year", type=int, action="append")
    ap.add_argument("--out-root", default=str(config.REBUILD_ROOT))
    args = ap.parse_args()

    keys = list(CHAINS[args.chain]) if args.chain else (args.dataset or [])
    if not keys:
        ap.error("give --chain or --dataset")
    years = args.year or sorted(config.FROZEN_SEASONS)
    paths = Paths(out_root=args.out_root)
    for key in keys:
        stitch(key, years, paths)


if __name__ == "__main__":
    main()
