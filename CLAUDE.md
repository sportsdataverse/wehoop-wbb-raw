# CLAUDE.md — wehoop-wbb-raw Development Guide

## Repo Overview

`wehoop-wbb-raw` is the Python-side scraper that pulls ESPN women's college
basketball schedules and per-game JSON, persists them to disk under
`wbb/schedules/` and `wbb/json/final/{game_id}.json`, and commits the
results back to this repo. Every push to `main` fires a `repository_dispatch`
that wakes up the downstream R parser in `wehoop-wbb-data`. This repo is the
authoritative cache of raw ESPN payloads — the parsing layer never re-hits
ESPN, it reads from here.

## Pipeline Position

```
ESPN APIs --[python scrape]--> wehoop-wbb-raw [HERE]
                                    | push trigger
                                    v
                               wehoop-wbb-data --[release upload]--> sportsdataverse-data
                                                                          | piggyback
                                                                          v
                                                                    wehoop R package
```

The push trigger is `.github/workflows/wehoop_wbb_data_trigger.yaml`, which
fires `repository_dispatch` event-type `daily_wbb_data` against
`sportsdataverse/wehoop-wbb-data`.

## Build & Development Commands

The repo is driven by `scripts/daily_wbb_scraper.sh`, which sequences
schedule scraping then per-game JSON scraping, then commits + pushes. All
seasons are integer years.

```sh
# Full daily flow for one or more seasons (the entry point CI uses)
bash scripts/daily_wbb_scraper.sh -s 2025 -e 2025 -r false

# Or call the scrapers directly when iterating
python3 python/scrape_wbb_schedules.py -s 2025 -e 2025 -r false
python3 python/scrape_wbb_json.py      -s 2025 -e 2025 -r false

# Helpers
python3 python/process_wbb_schedules.py
python3 python/add_game_links_to_schedule.py

# Phase 1 datasets (per-season rosters + per-athlete season stats)
python3 python/scrape_wbb_team_rosters.py  -s 2025 -e 2025 [-r]
python3 python/scrape_wbb_player_stats.py  -s 2025 -e 2025 [-r]

# Per-team season stats and per-season standings
python3 python/scrape_wbb_team_stats.py    -s 2025 -e 2025 [-r]
python3 python/scrape_wbb_standings.py     -s 2025 -e 2025 [-r]

# Per-game rosters and officials (per-game iteration; mirrors scrape_wbb_json.py shape)
python3 python/scrape_wbb_game_rosters.py  -s 2025 -e 2025 [-r]
python3 python/scrape_wbb_officials.py     -s 2025 -e 2025 [-r]
```

`-r true` forces re-scrape of games already on disk; `-r false` skips
existing files. Output paths the scrapers write under:

- `wbb/schedules/{rds,csv,parquet}/wbb_schedule_{year}.{ext}`
- `wbb/json/final/{game_id}.json` — final clean payload, consumed by `wehoop-wbb-data`
- `wbb/json/raw/{game_id}.json`   — raw ESPN response (kept for forensics)
- `wbb/errors/`                   — failed-game records
- `wbb/team_rosters/json/{season}/{team_id}.json`         — Phase 1: ESPN team-roster snapshots
- `wbb/player_season_stats/json/{season}/{athlete_id}.json` — Phase 1: ESPN per-athlete season stats
- `wbb/team_stats/json/{season}/{team_id}.json`           — ESPN per-team season stats (daily cadence)
- `wbb/standings/json/{season}.json`                      — ESPN per-season standings (daily cadence)
- `wbb/game_rosters/json/{game_id}.json`                  — ESPN per-game rosters (daily cadence; per-game iteration)
- `wbb/officials/json/{game_id}.json`                     — ESPN per-game officials (daily cadence; per-game iteration)

## Project Structure

```
python/
  scrape_wbb_schedules.py     # ESPN schedule scrape -> wbb/schedules/
  scrape_wbb_json.py          # Per-game JSON scrape -> wbb/json/final/{game_id}.json
  process_wbb_schedules.py    # Schedule post-processing
  add_game_links_to_schedule.py
scripts/
  daily_wbb_scraper.sh        # CI entry point
wbb/                          # Committed scraped output (consumed downstream)
.github/workflows/
  wehoop_wbb_data_trigger.yaml  # Fires repository_dispatch on push
  daily_wbb_raw.yml             # Umbrella daily scrape (cron + workflow_dispatch)
```

## Daily Umbrella Workflow

`.github/workflows/daily_wbb_raw.yml` is the in-repo cron entry point. It
runs every per-dataset Python scraper sequentially in one job and commits
the cumulative output in a single push, which then fires
`wehoop_wbb_data_trigger.yaml` exactly once per run.

- **Cadence**: `0 5 UTC` daily, gated to the in-season month/day windows
  used by `wehoop-wbb-data/daily_wbb.yml` (late October, November-December,
  January-March, early April). The 2-hour offset before the data repo's
  `0 7 UTC` parser gives the scrape time to land before the parser pulls.
- **Manual run**: `workflow_dispatch` accepts `start_year`, `end_year`,
  and `rescrape` (default `false`) inputs.
- **Scripts run, in order**: `scrape_wbb_schedules.py`, `scrape_wbb_json.py`,
  `scrape_wbb_team_rosters.py`, `scrape_wbb_player_stats.py`,
  `scrape_wbb_team_stats.py`, `scrape_wbb_standings.py`,
  `scrape_wbb_game_rosters.py`, `scrape_wbb_officials.py`. All are invoked
  with the canonical `--start_year`/`--end_year` flags plus `-r $RESCRAPE`.
- **Single push**: `git add wbb/` + one commit + one push at the end. This
  is intentional — every push to `main` fires
  `wehoop_wbb_data_trigger.yaml`, so one push per day means one downstream
  dispatch per day instead of eight.
- **Replaces**: `scripts/daily_wbb_scraper.sh` if/when CI moves wholly to
  GitHub Actions. The shell script is still callable locally and from
  external schedulers; nothing here removes it.

The Python scrapers depend on `sportsdataverse-py` (declared in
`requirements.txt`); they call `sdv.wbb.espn_wbb_pbp(game_id, raw=True)`
and similar helpers. Bug fixes to ESPN parsing belong in `sportsdataverse-py`
WBB modules — not here.

## Cross-Repo References

- Shared conventions and broader context: <https://github.com/sportsdataverse/wehoop/blob/main/CLAUDE.md>
- Python scraper internals (the SDK this repo calls): <https://github.com/sportsdataverse/sportsdataverse-py/blob/main/CLAUDE.md>
- Downstream parser: <https://github.com/sportsdataverse/wehoop-wbb-data>

## Project-Specific Gotchas

- `python/scrape_wbb_json.py` writes JSON under `wbb/json/final/{game_id}.json`. Downstream `wehoop-wbb-data` reads from `https://raw.githubusercontent.com/sportsdataverse/wehoop-wbb-raw/main/wbb/...`, so the file paths and commit-to-main are load-bearing.
- The per-push `wehoop_wbb_data_trigger.yaml` workflow only fires on `push` and `workflow_dispatch`. Force-pushes can land changes without firing downstream jobs — push normally.
- Large additions of `wbb/json/final/*.json` files inflate the repo. Don't reorganize the `wbb/` tree without coordinating the change in `wehoop-wbb-data`'s creation scripts (`R/espn_wbb_0[1-3]_*.R`).
- ESPN JSON schema drift is handled in `sportsdataverse-py` (the call boundary). If a scraper starts dropping fields, fix the SDK first; this repo should stay thin.

## Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scrape): add NCAA Tournament fallback IDs to scrape_wbb_schedules.py
fix(scrape): handle 503s in scrape_wbb_json without aborting the season loop
chore(deps): bump sportsdataverse-py pin in requirements.txt
ci: align push trigger with new workflow secret name
```

Prefer scoped subjects (`feat(scrape): ...`, `ci(trigger): ...`). Use
`type!:` or a `BREAKING CHANGE:` footer for breaking changes. Split
unrelated work into separate commits for reviewability.

**Important: Never include AI agents or assistants (e.g., Claude, Copilot, Cursor, GPT, Gemini) as co-authors on commits.** Omit all `Co-Authored-By` trailers referencing AI tools. This applies whether the change was generated, refactored, or reviewed with AI assistance — the human author is the sole attributable contributor.
