"""Compile every per-season schedule into the master + coverage index.

Runs LAST in the daily scrape. It stamps each season file with the ``has_*``
capture flags (which requires steps 02-09 to have finished), then unions the
season files into the master and aggregates the coverage table.

Previously the master was glued together inside step 01, which runs first and
therefore could not know what the rest of the run had captured.

Example:
    Rebuild everything::

        uv run python python/espn_wbb_99_schedule_master_creation.py

    Only restamp and rebuild for a season range::

        uv run python python/espn_wbb_99_schedule_master_creation.py -s 2024 -e 2026
"""

from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from wbb_raw_scrape.master import build_coverage, build_master
from wbb_raw_scrape.schedule import add_capture_columns

REPO_ROOT = Path(__file__).resolve().parents[1]
LEAGUE = "wbb"
SEASON_DIR = REPO_ROOT / LEAGUE / "schedules" / "parquet"
MASTER_PATH = REPO_ROOT / LEAGUE / f"{LEAGUE}_schedule_master.parquet"
COVERAGE_PATH = REPO_ROOT / LEAGUE / f"{LEAGUE}_schedule_coverage.parquet"


def _season_of(path: Path) -> int | None:
    stem = path.stem.rsplit("_", 1)[-1]
    return int(stem) if stem.isdigit() else None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--start_year", "-s", type=int, default=None)
    parser.add_argument("--end_year", "-e", type=int, default=None)
    args = parser.parse_args(argv)

    paths = sorted(SEASON_DIR.glob(f"{LEAGUE}_schedule_*.parquet"))
    if not paths:
        print(f"::error ::no season schedules under {SEASON_DIR}")
        return 1

    # Restamp only the requested seasons, but always union ALL of them: the
    # master is the whole archive, not just this run's window.
    lo = args.start_year if args.start_year is not None else -1
    hi = args.end_year if args.end_year is not None else 10**9
    if args.start_year is not None and args.end_year is None:
        hi = args.start_year

    frames: list[pl.DataFrame] = []
    restamped = 0
    for path in paths:
        frame = pl.read_parquet(path)
        season = _season_of(path)
        if season is not None and lo <= season <= hi:
            frame = add_capture_columns(frame, root=REPO_ROOT, league=LEAGUE)
            frame.write_parquet(path)
            restamped += 1
        frames.append(frame)

    master = build_master(frames)
    coverage = build_coverage(master)
    master.write_parquet(MASTER_PATH)
    coverage.write_parquet(COVERAGE_PATH)

    print(f"restamped {restamped} season file(s)")
    print(f"master:   {master.height} games across {len(paths)} seasons -> {MASTER_PATH.name}")
    print(f"coverage: {coverage.height} rows -> {COVERAGE_PATH.name}")
    for flag in (c for c in master.columns if c.startswith("has_")):
        print(f"  {flag}: {master[flag].sum()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
