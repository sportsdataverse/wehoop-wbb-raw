# wehoop-wbb-raw Copilot Instructions

## Project Context

This repo is the Python ESPN-scrape stage for women's college basketball.
It writes per-game JSON under `wbb/json/final/{game_id}.json` and commits
results to `main`. Every push wakes the downstream R parser in
`wehoop-wbb-data` via `repository_dispatch` (event-type `daily_wbb_data`,
defined in `.github/workflows/wehoop_wbb_data_trigger.yaml`).

Pipeline: `ESPN -> wehoop-wbb-raw [HERE] -> wehoop-wbb-data -> sportsdataverse-data -> wehoop`.

## Repository Workflow

- Branch from `main`; `main` is the default and release branch.
- The CI entry point is `scripts/daily_wbb_scraper.sh -s <START> -e <END> -r <true|false>`.
- Scrapers shell out to `sportsdataverse-py`. Fix ESPN parser bugs upstream there, not here.
- Don't reorganize the `wbb/` output tree without aligning `wehoop-wbb-data/R/espn_wbb_0[1-3]_*.R`.

## Build & Development Commands

```sh
bash scripts/daily_wbb_scraper.sh -s 2025 -e 2025 -r false
python3 python/scrape_wbb_schedules.py    -s 2025 -e 2025 -r false
python3 python/scrape_wbb_json.py         -s 2025 -e 2025 -r false
python3 python/scrape_wbb_team_rosters.py -s 2025 -e 2025
python3 python/scrape_wbb_player_stats.py -s 2025 -e 2025
python3 python/scrape_wbb_team_stats.py   -s 2025 -e 2025
python3 python/scrape_wbb_standings.py    -s 2025 -e 2025
python3 python/scrape_wbb_game_rosters.py -s 2025 -e 2025
python3 python/scrape_wbb_officials.py    -s 2025 -e 2025
```

`-r true` forces re-scrape; `-r false` skips files already on disk. Outputs:

- `wbb/schedules/{rds,csv,parquet}/wbb_schedule_{year}.{ext}`
- `wbb/json/final/{game_id}.json` (consumed downstream)
- `wbb/json/raw/{game_id}.json`, `wbb/errors/` (forensics)
- `wbb/team_rosters/json/{season}/{team_id}.json` (Phase 1)
- `wbb/player_season_stats/json/{season}/{athlete_id}.json` (Phase 1)
- `wbb/team_stats/json/{season}/{team_id}.json` — ESPN per-team season stats (daily)
- `wbb/standings/json/{season}.json` — ESPN per-season standings (daily)
- `wbb/game_rosters/json/{game_id}.json` — ESPN per-game rosters (daily; per-game iteration)
- `wbb/officials/json/{game_id}.json` — ESPN per-game officials (daily; per-game iteration)

## Code Style

- Follow the parent SDK's Python conventions: snake_case, 4-space indent.
- Prefer `pathlib.Path`, `concurrent.futures` for parallelism, `tqdm` for progress.
- Don't add bespoke ESPN parsing here — call into `sportsdataverse.wbb.*` and persist its output.
- Keep `requirements.txt` minimal; avoid adding heavy ML/analytical deps.

## Daily Umbrella Workflow

`.github/workflows/daily_wbb_raw.yml` runs every WBB scraper sequentially on
a single GitHub Actions cron and commits the cumulative output in one push,
which fires `wehoop_wbb_data_trigger.yaml` exactly once per run.

- Cron `0 5 UTC` daily, gated to the in-season windows used by
  `wehoop-wbb-data/daily_wbb.yml` (late Oct, Nov-Dec, Jan-Mar, early Apr).
- `workflow_dispatch` inputs: `start_year`, `end_year`, `rescrape`.
- Scripts in order: `scrape_wbb_schedules.py`, `scrape_wbb_json.py`,
  `scrape_wbb_team_rosters.py`, `scrape_wbb_player_stats.py`,
  `scrape_wbb_team_stats.py`, `scrape_wbb_standings.py`,
  `scrape_wbb_game_rosters.py`, `scrape_wbb_officials.py`.
- Single `git add wbb/` + commit + push at the end keeps the downstream
  dispatch count to one per run.
- Eventually replaces `scripts/daily_wbb_scraper.sh` for CI use; the shell
  script remains for local + external scheduler invocation.

## Cross-Repo References

- Shared conventions: <https://github.com/sportsdataverse/wehoop/blob/main/CLAUDE.md>
- SDK internals: <https://github.com/sportsdataverse/sportsdataverse-py/blob/main/CLAUDE.md>

## Conventional Commits

Use: `type(scope): description`. Common types: `feat`, `fix`, `chore`, `ci`, `docs`, `refactor`. Use `type!:` or a `BREAKING CHANGE:` footer for breaking changes.

**Important: Never include AI agents or assistants (e.g., Claude, Copilot, Cursor, GPT, Gemini) as co-authors on commits.** Omit all `Co-Authored-By` trailers referencing AI tools. This applies whether the change was generated, refactored, or reviewed with AI assistance — the human author is the sole attributable contributor.
