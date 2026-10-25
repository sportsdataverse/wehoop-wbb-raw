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

import pandas as pd
import polars as pl
from sportsdataverse.scrape.espn.ids import with_int64_ids
from sportsdataverse.scrape.espn.master import build_coverage, build_master
from sportsdataverse.scrape.espn.schedule import add_capture_columns

REPO_ROOT = Path(__file__).resolve().parents[1]
LEAGUE = "wbb"
SEASON_DIR = REPO_ROOT / LEAGUE / "schedules" / "parquet"
MASTER_PATH = REPO_ROOT / LEAGUE / f"{LEAGUE}_schedule_master.parquet"
COVERAGE_PATH = REPO_ROOT / LEAGUE / f"{LEAGUE}_schedule_coverage.parquet"

# Published id dtype: Int64 for every `id` / `*_id` column of the schedule (id, type_id,
# status_type_id, game_id, home_id, away_id, venue_id, home_venue_id, away_venue_id,
# home_conference_id, away_conference_id, groups_id, tournament_id), whatever dtype sdv-py
# returns (String before its Int64 id contract, Int64 after it). The .rds gets R integer.
INT32_MAX = 2**31 - 1


def is_id_column(name: str) -> bool:
    return name == "id" or name.endswith("_id")


def _id_prep(df: pl.DataFrame, c: str) -> pl.Expr:
    dtype = df.schema[c]
    if dtype == pl.String:
        return pl.col(c).str.strip_chars().replace("", None)
    if dtype.is_float():
        return pl.col(c).fill_nan(None)
    return pl.col(c).cast(pl.Int64) if dtype == pl.Null else pl.col(c)


def cast_ids_int64(df: pl.DataFrame | pd.DataFrame, *, rds: bool = False):
    """Cast every id column to Int64, strictly; a pandas frame comes back pandas.

    Strings are stripped and ``""`` becomes null; a whole-number float is accepted and NaN
    becomes null. Anything else (``"abc"``, ``1.5``) raises ``ValueError`` instead of nulling.
    ``rds=True`` (pandas only) returns nullable ``Int32`` instead: pyreadr writes that as R
    integer with NA, and cannot write an ``Int64`` NA at all.
    """
    if isinstance(df, pd.DataFrame):
        out = df.copy()
        for c in filter(is_id_column, out.columns):
            col = cast_ids_int64(pl.DataFrame({c: pl.from_pandas(out[c])})).get_column(c)
            if rds and (col.abs() > INT32_MAX).any():  # Int64 -> Int32 would wrap silently
                raise ValueError(f"{c!r} exceeds the R integer range")
            out[c] = pd.array(col.to_list(), dtype="Int32" if rds else "Int64")
        return out
    cols = [c for c in df.columns if is_id_column(c)]
    return with_int64_ids(df.with_columns(_id_prep(df, c) for c in cols), *cols)


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
        frame = cast_ids_int64(pl.read_parquet(path))
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
