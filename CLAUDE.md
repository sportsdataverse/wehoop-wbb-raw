# CLAUDE.md — wehoop-wbb-raw

Python scraper for ESPN women's college basketball (WBB). Commits raw per-game
ESPN JSON to git; the paired `wehoop-wbb-data` (R) reshapes it into release
parquet/csv/rds consumed by the `wehoop` R package's `load_wbb_*()` loaders.

Pipeline: `ESPN -> wehoop-wbb-raw [HERE] --push--> wehoop-wbb-data --release--> sportsdataverse-data --> wehoop`.

## Commands (verified)

Driven by `scripts/daily_wbb_scraper.sh` (getopts `-s -e -r`; loops seasons,
commits + pushes). Scrapers take `--start_year/-s`, `--end_year/-e`,
`--rescrape/-r` (Python argparse defaults `-r`/`-p` to `True`; the shell script
defaults `-r` to `true`). Seasons are end-of-season YYYY (2025 = 2024-25).

```sh
bash scripts/daily_wbb_scraper.sh -s 2025 -e 2025 -r false   # full daily flow
python3 python/scrape_wbb_schedules.py -s 2025 -e 2025 -r false
python3 python/scrape_wbb_json.py      -s 2025 -e 2025 -r false   # per-game PBP JSON
# also: scrape_wbb_team_rosters / _player_stats / _team_stats / _standings /
#       _game_rosters / _officials  (same -s -e -r flags)
# helpers: process_wbb_schedules.py, add_game_links_to_schedule.py
```

`-r true` re-scrapes games already on disk; `-r false` skips them. Scrapers
depend on `sportsdataverse-py` (`requirements.txt`) and call
`sdv.wbb.espn_wbb_*(..., raw=True)` — fix ESPN parsing in `sportsdataverse-py`, not here.

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
- WBB has no draft; any future annual dataset needs its own scraper + trigger.
- Never add AI co-author trailers to commits. Use Conventional Commits (`feat(scrape):`, `fix(scrape):`, `ci:`).
