"""Capture-state and URL columns for the per-season schedule files.

The per-season schedule is the ORIGIN of every flag. The master does not
compute flags -- it inherits them by union, so a flag added here appears in the
master and the coverage index with no further wiring.

This repo carries ``has_*`` (capture) flags only. ``in_*`` (build) flags are a
wehoop-wbb-data fact; stamping them here would make the archive read the data
repo, a dependency in the wrong direction that goes stale whenever either side
rebuilds alone.
"""

from __future__ import annotations

import os
from pathlib import Path

import polars as pl

from wbb_raw_scrape.ids import with_int64_ids
from wbb_raw_scrape.paths import raw_github_url

REPO = "wehoop-wbb-raw"

#: column stem -> tree segments under ``<league>/``. One entry per per-game
#: payload family the archive holds.
FAMILIES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("game_json", ("json", "final")),
    ("game_json_raw", ("json", "raw")),
    ("game_rosters_json", ("game_rosters", "json")),
    ("officials_json", ("officials", "json")),
)

#: Families that get a ``has_*`` flag. ``game_json_raw`` shares
#: ``has_game_json``: both are written by step 02 in the same call, so their
#: presence never diverges and a second flag would only be able to lie.
FLAGGED = ("game_json", "game_rosters_json", "officials_json")

ID_COLUMNS = ("game_id", "home_id", "away_id", "venue_id")


def add_capture_columns(
    df: pl.DataFrame, *, root: Path | str, league: str = "wbb", repo: str = REPO
) -> pl.DataFrame:
    """Add per-family URL columns and ``has_*`` capture flags to a schedule.

    Args:
        df: A season schedule frame containing ``game_id``.
        root: Repo root the ``<league>/`` tree hangs off.
        league: Tree prefix, ``"wbb"`` here.
        repo: GitHub repo name used to build the public raw URLs.

    Returns:
        The frame with ids canonicalized to Int64, one ``<stem>_url`` column
        per family, and a ``has_<stem>`` boolean for each flagged family.

    URLs are emitted for every row whether or not the file exists -- the
    ``has_*`` flag is the truth, the URL is the address. Filenames are built
    from the integer id, so a float-origin id can never address ``123.0.json``.
    """
    root = Path(root)
    out = with_int64_ids(df, *ID_COLUMNS)
    game_ids = out["game_id"].to_list()

    columns: list[pl.Series] = []
    for stem, segments in FAMILIES:
        columns.append(
            pl.Series(
                f"{stem}_url",
                [
                    None if gid is None else raw_github_url(repo, league, *segments, f"{gid}.json")
                    for gid in game_ids
                ],
                dtype=pl.Utf8,
            )
        )
        if stem in FLAGGED:
            captured = _captured_ids(root / league / Path(*segments))
            columns.append(
                pl.Series(
                    f"has_{stem}",
                    [gid is not None and gid in captured for gid in game_ids],
                    dtype=pl.Boolean,
                )
            )
    return out.with_columns(columns)


def _captured_ids(directory: Path) -> set[int]:
    """Every game id present in a family directory, as one listing.

    A per-game ``Path.exists()`` would be ~400k syscalls across the full
    archive (133k games x 3 families) and made the daily step crawl on Windows.
    One scandir per family is O(files) and answers every membership test.
    """
    if not directory.is_dir():
        return set()
    ids: set[int] = set()
    with os.scandir(directory) as entries:
        for entry in entries:
            name, _, ext = entry.name.rpartition(".")
            if ext == "json" and name.isdigit():
                ids.add(int(name))
    return ids
