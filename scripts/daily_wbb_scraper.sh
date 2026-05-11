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
        python3 python/scrape_wbb_schedules.py    -s $i -e $i -r $RESCRAPE
        python3 python/scrape_wbb_json.py         -s $i -e $i -r $RESCRAPE
        python3 python/scrape_wbb_team_rosters.py -s $i -e $i -r $RESCRAPE
        python3 python/scrape_wbb_player_stats.py -s $i -e $i -r $RESCRAPE
        python3 python/scrape_wbb_team_stats.py   -s $i -e $i -r $RESCRAPE
        python3 python/scrape_wbb_standings.py    -s $i -e $i -r $RESCRAPE
        python3 python/scrape_wbb_game_rosters.py -s $i -e $i -r $RESCRAPE
        python3 python/scrape_wbb_officials.py    -s $i -e $i -r $RESCRAPE
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