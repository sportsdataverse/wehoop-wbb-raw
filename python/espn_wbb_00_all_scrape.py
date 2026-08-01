"""Run every WBB raw scraper for a season range, in dependency order.

Mirrors the step order in ``.github/workflows/daily_wbb_raw.yml`` and
``scripts/daily_wbb_scraper.sh`` so a local run and a CI run produce the same
on-disk output.

One dead scraper must not stop the others -- whatever DID scrape should still
be committed -- but the run must go RED at the end so somebody looks. That is
the same contract the shell script implements with its failure file.

Example:
    Scrape one season::

        python python/espn_wbb_00_all_scrape.py --start_year 2026

    Force a re-fetch of payloads already on disk::

        python python/espn_wbb_00_all_scrape.py -s 2026 -e 2026 -r true
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from wbb_raw_scrape.cli import season_args

HERE = Path(__file__).resolve().parent

# Run order. 01 writes the season schedule that 02 reads to enumerate games.
STEPS = [
    "espn_wbb_01_schedules_scrape.py",
    "espn_wbb_02_pbp_scrape.py",
    "espn_wbb_03_team_rosters_scrape.py",
    "espn_wbb_04_player_core_scrape.py",
    "espn_wbb_05_player_season_stats_scrape.py",
    "espn_wbb_06_team_season_stats_scrape.py",
    "espn_wbb_07_standings_scrape.py",
    "espn_wbb_08_game_rosters_scrape.py",
    "espn_wbb_09_officials_scrape.py",
]


# Every scraper takes -s/-e, but the flag that controls re-fetching is spelled
# two ways in this repo: --rescrape on the schedule/pbp pair, --rerun_existing
# on the rest. Both accept -r, so -r is what we pass.
def main() -> int:
    args = season_args()
    failed: list[str] = []
    for step in STEPS:
        cmd = [
            sys.executable,
            str(HERE / step),
            "--start_year",
            str(args.start_year),
            "--end_year",
            str(args.end_year),
            "-r",
            "true" if args.rescrape else "false",
        ]
        print(f"::group::{step}", flush=True)
        result = subprocess.run(cmd)
        print("::endgroup::", flush=True)
        if result.returncode != 0:
            print(f"::warning ::{step} exited with code {result.returncode}", flush=True)
            failed.append(step)
    for step in failed:
        print(f"::error ::{step} failed", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
