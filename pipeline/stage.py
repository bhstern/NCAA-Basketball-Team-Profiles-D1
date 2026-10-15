"""
Shared stage plumbing — the `--year` command line and the gate result type.

A build stage is `run(year, paths) -> Path` (the file it wrote).
A check stage is `run(year, paths) -> GateResult`.

Checks are ADVISORY for now: they print everything the original scripts printed and
report pass/fail, but never stop a run. They must become blocking before the nightly
cron (Phase 6) — flip `blocking` there, after the check-script fixes are approved.
"""

import argparse
from dataclasses import dataclass, field

from . import config
from .paths import Paths


@dataclass
class GateResult:
    name: str
    year: int
    passed: object                    # True / False / None (= not evaluated)
    blocking: bool = False
    messages: list = field(default_factory=list)

    @property
    def status(self):
        if self.passed is None:
            return "NOT EVALUATED"
        return "PASS" if self.passed else "FAIL"

    def summary(self):
        kind = "blocking" if self.blocking else "advisory"
        lines = [f"[GATE {self.status}] {self.name} {self.year} ({kind})"]
        lines += [f"    - {m}" for m in self.messages]
        return "\n".join(lines)


def stage_main(run, doc):
    """Standard CLI for a stage: --year (repeatable), --out-root, --raw-root."""
    ap = argparse.ArgumentParser(description=doc, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, action="append", required=True)
    ap.add_argument("--out-root", default=str(config.REBUILD_ROOT),
                    help="Output root (default: Master Datasets/_rebuild sandbox)")
    ap.add_argument("--raw-root", default=str(config.RAW_ROOT),
                    help="Raw input root (frozen seasons only accept the hand-built raw root)")
    args = ap.parse_args()
    paths = Paths(raw_root=args.raw_root, out_root=args.out_root)
    results = []
    for year in args.year:
        result = run(year, paths)
        if isinstance(result, GateResult):
            print(result.summary())
        results.append(result)
    return results
