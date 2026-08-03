#!/bin/bash
# Scrape raw WBB daily datasets per season:
#   schedules, per-game JSON (PBP), team rosters, player season stats,
#   team season stats, standings, per-game rosters, per-game officials.
#
# Mirrors the step order in .github/workflows/daily_wbb_raw.yml so local
# runs and CI runs produce the same on-disk output. WBB has no draft;
# any future annual datasets should get their own script.
#
# Usage: bash scripts/daily_wbb_scraper.sh -s 2025 -e 2025 [-r false]

while getopts s:e:r: flag
do
    case "${flag}" in
        s) START_YEAR=${OPTARG};;
        e) END_YEAR=${OPTARG};;
        r) RESCRAPE=${OPTARG};;
    esac
done
RESCRAPE=${RESCRAPE:-true}
echo "Rescrape set to: $RESCRAPE"
mkdir -p logs

# Resolve the interpreter once, via the shared resolver. Deliberately not
# `uv run`: that resyncs the venv to the lockfile mid-sweep (it can swap
# sportsdataverse under a running multi-hour scrape) and makes uv a RUNTIME
# dependency of every scrape. Build the venv ahead of time with `uv sync`.
# shellcheck source=scripts/_venv.sh
. "$(dirname "${BASH_SOURCE[0]}")/_venv.sh"
PY="$SDV_PY"
echo "Interpreter: $PY"

# Scraper failures used to be swallowed: each scraper ran bare, so a crash left
# the loop running, the partial day got committed, and the job still exited 0.
# Four scrapers sat dead for two sportsdataverse-py release cycles that way --
# aborting at import on a renamed symbol, every day, silently green.
#
# run_scraper keeps that resilience (one dead scraper must not stop the others,
# and whatever DID scrape should still be committed) but records the failure so
# the run goes RED at the end and someone actually looks.
#
# NOTE: the scrapers run inside `{ ... } | tee`, and a pipe is a SUBSHELL -- a
# counter variable incremented in there is discarded when it exits. That's why
# failures go to a FILE. Do not "simplify" this to a FAILED=$((FAILED+1)) var.
FAILLOG=$(mktemp "/tmp/wehoop_wbb_raw_failures.XXXXXX")
trap 'rm -f "$FAILLOG"' EXIT

run_scraper() {
    local label="$1"; shift
    "$@"
    local rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "!!! SCRAPER FAILED (rc=$rc): $label"
        echo "$label rc=$rc" >> "$FAILLOG"
    fi
    return 0
}
for i in $(seq "${START_YEAR}" "${END_YEAR}")
do
    LOGFILE="logs/wehoop_wbb_raw_logfile_${i}.log"
    TMPLOG=$(mktemp "/tmp/wehoop_wbb_raw_logfile_${i}.XXXXXX.log")
    echo "=== Processing season $i ==="
    # Tee inside the block writes to /tmp (untracked) so the `git pull` calls
    # don't trip over their own log output being written to a tracked file.
    {
        git pull >> /dev/null
        git config --local user.email "action@github.com"
        git config --local user.name "Github Action"
        run_scraper schedules    $PY python/espn_wbb_01_schedules_scrape.py           -s $i -e $i -r $RESCRAPE
        run_scraper pbp          $PY python/espn_wbb_02_pbp_scrape.py                 -s $i -e $i -r $RESCRAPE
        run_scraper team_rosters $PY python/espn_wbb_08_team_rosters_scrape.py        -s $i -e $i -r $RESCRAPE
        run_scraper player_core  $PY python/espn_wbb_09_player_core_scrape.py         -s $i -e $i -r $RESCRAPE
        run_scraper player_stats $PY python/espn_wbb_06_player_season_stats_scrape.py -s $i -e $i -r $RESCRAPE
        run_scraper team_stats   $PY python/espn_wbb_07_team_season_stats_scrape.py   -s $i -e $i -r $RESCRAPE
        run_scraper standings    $PY python/espn_wbb_03_standings_scrape.py           -s $i -e $i -r $RESCRAPE
        run_scraper game_rosters $PY python/espn_wbb_04_game_rosters_scrape.py        -s $i -e $i -r $RESCRAPE
        run_scraper officials    $PY python/espn_wbb_10_officials_scrape.py           -s $i -e $i -r $RESCRAPE
        # Last: stamps has_* capture flags onto the season schedule, then
        # unions every season into the master + coverage index.
        run_scraper master       $PY python/espn_wbb_99_schedule_master_creation.py   -s $i -e $i
        git pull >> /dev/null
        git add wbb/* >> /dev/null
        git pull >> /dev/null
        git add . >> /dev/null
        git commit -m "WBB Raw Updated (Start: $i End: $i)" || echo "No changes to commit"
        git pull >> /dev/null
        git push >> /dev/null
    } 2>&1 | tee "$TMPLOG"

    # Block is finished and pushed; tee has closed $TMPLOG. Now copy the log
    # into its tracked location and commit/push it on its own.
    cp "$TMPLOG" "$LOGFILE"
    git pull --rebase >> /dev/null || true
    git add "$LOGFILE"
    git commit -m "WBB Raw log update (Start: $i End: $i)" >> /dev/null || echo "No log changes to commit"
    git push >> /dev/null
    rm -f "$TMPLOG"
done

# Everything that could scrape has scraped, and every partial result is
# committed and pushed -- only now do we decide the exit code. A dead scraper
# must turn the run RED; a green run over silently-missing data is worse than
# an obvious failure.
if [ -s "$FAILLOG" ]; then
    echo ""
    echo "=================================================="
    echo "SCRAPER FAILURES (data for these is NOT up to date)"
    cat "$FAILLOG"
    echo "=================================================="
    exit 1
fi
echo "All scrapers OK."