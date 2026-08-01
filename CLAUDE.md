# CLAUDE.md — wehoop-wbb-raw

Python scraper for ESPN women's college basketball (WBB). Commits raw per-game
ESPN JSON to git; the paired `wehoop-wbb-data` (R) reshapes it into release
parquet/csv/rds consumed by the `wehoop` R package's `load_wbb_*()` loaders.

Pipeline: `ESPN -> wehoop-wbb-raw [HERE] --push--> wehoop-wbb-data --release--> sportsdataverse-data --> wehoop`.

## Commands (verified)

Driven by `scripts/daily_wbb_scraper.sh` (getopts `-s -e -r`; loops seasons,
commits + pushes). Every scraper takes `--start_year/-s`, `--end_year/-e`, and
`-r` (spelled `--rescrape` on 01/02, `--rerun_existing` on the rest).
**`-r` defaults to false everywhere** — the raw tree is the checkpoint.
Seasons are end-of-season YYYY (2025 = 2024-25).

Script numbers are run order; 01 writes the season schedule that 02 reads.

| # | Script | Raw tree written |
|---:|---|---|
| 00 | `espn_wbb_00_all_scrape.py` | runs 01–09 in order |
| 01 | `espn_wbb_01_schedules_scrape.py` | `wbb/schedules/{parquet,rds}/` |
| 02 | `espn_wbb_02_pbp_scrape.py` | `wbb/json/{raw,final}/` |
| 03 | `espn_wbb_03_team_rosters_scrape.py` | `wbb/team_rosters/json/{season}/` |
| 04 | `espn_wbb_04_player_core_scrape.py` | `wbb/player_core/json/` |
| 05 | `espn_wbb_05_player_season_stats_scrape.py` | `wbb/player_season_stats/json/{season}/` |
| 06 | `espn_wbb_06_team_season_stats_scrape.py` | `wbb/team_stats/json/{season}/` |
| 07 | `espn_wbb_07_standings_scrape.py` | `wbb/standings/json/` |
| 08 | `espn_wbb_08_game_rosters_scrape.py` | `wbb/game_rosters/json/` |
| 09 | `espn_wbb_09_officials_scrape.py` | `wbb/officials/json/` |

```sh
bash scripts/daily_wbb_scraper.sh -s 2025 -e 2025 -r false   # full daily flow
uv run python python/espn_wbb_00_all_scrape.py -s 2025 -e 2025
uv run python python/espn_wbb_02_pbp_scrape.py -s 2025 -e 2025   # per-game PBP JSON
```

`-r true` re-scrapes payloads already on disk; `-r false` (the default) skips
them. Dependencies live in `pyproject.toml` + `uv.lock` (there is no
`requirements.txt`). Scrapers call `sdv.wbb.espn_wbb_*(..., raw=True)` — fix
ESPN parsing in `sportsdataverse-py`, not here.

## Outputs (committed to git, under `wbb/`)

- `wbb/schedules/{rds,csv,parquet}/wbb_schedule_{year}.{ext}`
- `wbb/json/final/{game_id}.json` — clean payload consumed by `wehoop-wbb-data`
- `wbb/json/raw/{game_id}.json` — raw ESPN response (forensics); `wbb/errors/` — failed games
- `wbb/{team_rosters,player_season_stats,team_stats,standings}/json/...` (season-keyed)
- `wbb/{game_rosters,officials}/json/{game_id}.json` (per-game)

## CI

- `.github/workflows/daily_wbb_raw.yml` — cron (in-season windows, `30 6 UTC`,
  2h before the data repo's `0 7 UTC`); runner `[self-hosted, sdv-droplet]`;
  runs all scrapers then one `git add wbb/` + commit + push. `workflow_dispatch`
  inputs `start_year`/`end_year`/`rescrape`.
- `.github/workflows/wehoop_wbb_data_trigger.yaml` — on push to `wbb/**`, fires
  `repository_dispatch` event-type `daily_wbb_data` at `sportsdataverse/wehoop-wbb-data`,
  passing the commit message as client-payload. One push/day = one downstream dispatch.

## Gotchas

- Daily commit subject `"WBB Raw Updated (Start: $i End: $i)"` is load-bearing —
  the data repo regex-extracts the years from `Start:`/`End:`. Don't restyle it.
- `-raw` commits raw per-game JSON to git intentionally (the SDV pattern); the tree is large by design.
- **Never `argparse(type=bool)`.** bash passes the string `"false"` and
  `bool("false")` is `True`. Two scrapers carried it with `default=True`, so
  every daily run re-downloaded all ~129k game summaries from ESPN. Use
  `wbb_raw_scrape.cli.str2bool`; `tests/test_scripts_importable.py` has an AST
  check that fails the build if it comes back.
- **Never persist a provider error body.** ESPN answers failures with HTTP 200
  and an error payload (`{"code":3001,"detail":"timeout..."}` or a Spring-style
  `{"error","message","status",...}`), which is not an exception. 21 such files
  were committed and, because the raw tree is the checkpoint, stayed permanently
  empty. All writes go through `wbb_raw_scrape.persist.write_payload`, which
  refuses them and never truncates an existing good capture.
- Dependencies are `pyproject.toml` + `uv.lock` only. When adding an import,
  add the dependency in the same change — an import audit of `python/*.py` is
  what caught `pyreadr`/`pandas`/`numpy` going missing.
- WBB has no draft; any future annual dataset needs its own scraper + trigger.
- Never add AI co-author trailers to commits. Use Conventional Commits (`feat(scrape):`, `fix(scrape):`, `ci:`).
