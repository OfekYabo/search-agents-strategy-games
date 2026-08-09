#!/bin/bash
# Tournament status. Designed to be run from the Windows host with:
#
#   multipass exec tournament -- /home/ubuntu/search-agents-strategy-games/status.sh
#
# Prints service state, progress toward 2700 games, throughput, ETA, and
# explicit STALL / RESTART-LOOP verdicts so no interpretation is needed.

DIR=/home/ubuntu/search-agents-strategy-games
RAW=$DIR/results/v2
LOG=$DIR/results/tournament.log
TOTAL=2700

# What this run is SUPPOSED to be. Checked against three independent places
# below, because the version is invisible at the point you type
# `systemctl start` - it is baked into the unit's ExecStart - and finding out
# after ten hours that the wrong agents ran is the expensive way to learn it.
EXPECT_VERSION=v2

# Games are only counted once their commit marker (the games.csv row) is
# durable, so this never over-reports work that a crash would discard.
if [ -f "$RAW/games.csv" ]; then
    DONE=$(( $(wc -l < "$RAW/games.csv") - 1 ))
    MOVES=$(( $(wc -l < "$RAW/moves.csv" 2>/dev/null || echo 1) - 1 ))
    AGE=$(( $(date +%s) - $(stat -c %Y "$RAW/games.csv") ))
else
    DONE=0; MOVES=0; AGE=-1
fi
[ "$DONE" -lt 0 ] && DONE=0

STATE=$(systemctl is-active tournament)
ENABLED=$(systemctl is-enabled tournament 2>/dev/null)
NRESTARTS=$(systemctl show tournament -p NRestarts --value)
RESULT=$(systemctl show tournament -p Result --value)
START=$(systemctl show tournament -p ExecMainStartTimestamp --value)

echo "=============================================================="
echo " TOURNAMENT STATUS            $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=============================================================="
echo " service : $STATE ($ENABLED)   restarts: $NRESTARTS   result: $RESULT"
echo " started : $START"

# ---- which agent version is actually running ------------------------
# Three independent sources. The unit says what was configured, run_meta
# says what the process recorded at startup, and games.csv says what the
# finished games were actually played with. Agreement is the check.
UNIT_VERSION=$(systemctl cat tournament 2>/dev/null \
    | sed -n 's/.*--agent-version[= ]\([^ ]*\).*/\1/p' | head -1)
[ -z "$UNIT_VERSION" ] && UNIT_VERSION="v1(default)"

META_VERSION="-"
[ -f "$RAW/run_meta.json" ] && META_VERSION=$(python3 -c \
    "import json,sys;print(json.load(open(sys.argv[1]))['agent_version'])" \
    "$RAW/run_meta.json" 2>/dev/null || echo "?")

DATA_VERSION="-"
if [ -f "$RAW/games.csv" ]; then
    DATA_VERSION=$(python3 -c "
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
seen = sorted({(r.get('agent_first_version') or 'v1') for r in rows}
              | {(r.get('agent_second_version') or 'v1') for r in rows})
print(','.join(seen) if seen else '-')" "$RAW/games.csv" 2>/dev/null || echo "?")
fi

echo " version : unit=$UNIT_VERSION  recorded=$META_VERSION  in data=$DATA_VERSION   (expect $EXPECT_VERSION)"
echo " output  : $RAW"

VERSION_BAD=""
case "$UNIT_VERSION" in
    "$EXPECT_VERSION") ;;
    *) VERSION_BAD="unit says $UNIT_VERSION" ;;
esac
[ "$META_VERSION" != "-" ] && [ "$META_VERSION" != "$EXPECT_VERSION" ] \
    && VERSION_BAD="$VERSION_BAD; run_meta says $META_VERSION"
[ "$DATA_VERSION" != "-" ] && [ "$DATA_VERSION" != "$EXPECT_VERSION" ] \
    && VERSION_BAD="$VERSION_BAD; games.csv says $DATA_VERSION"

if [ -n "$VERSION_BAD" ]; then
    echo
    echo " >>> WRONG AGENT VERSION: $VERSION_BAD"
    echo "     Expected $EXPECT_VERSION. STOP NOW rather than spend ten hours"
    echo "     measuring the wrong agents:"
    echo "       sudo systemctl stop tournament"
    echo "     Then check ExecStart in /etc/systemd/system/tournament.service,"
    echo "     and delete $RAW before restarting - a resumed run would keep the"
    echo "     games already played with the wrong version."
fi
echo " uptime  : $(uptime -p)   load:$(cut -d' ' -f1-3 /proc/loadavg | sed 's/^/ /')"
echo

PCT=$(awk "BEGIN{printf \"%.1f\", 100*$DONE/$TOTAL}")
echo " progress: $DONE / $TOTAL games  (${PCT}%)   $MOVES move rows"

# Bar
FILLED=$(awk "BEGIN{printf \"%d\", 50*$DONE/$TOTAL}")
printf " ["
for i in $(seq 1 50); do [ "$i" -le "$FILLED" ] && printf "#" || printf "."; done
printf "]\n"

# Throughput and ETA, measured over the service's current uptime.
SEC=$(systemctl show tournament -p ExecMainStartTimestampMonotonic --value)
NOW=$(awk '{printf "%d", $1*1000000}' /proc/uptime)
ELAPSED=$(( (NOW - SEC) / 1000000 ))
# Only meaningful with no restarts: ExecMainStartTimestamp resets on restart
# while DONE keeps counting every game ever finished, which would inflate the
# rate and shrink the ETA after a crash. Suppress it rather than mislead.
if [ "$STATE" = "active" ] && [ "$NRESTARTS" -gt 0 ]; then
    echo " rate    : not shown - the service restarted $NRESTARTS time(s), so elapsed"
    echo "           time no longer covers all $DONE games. Compare two status.sh"
    echo "           readings 10 min apart instead."
elif [ "$STATE" = "active" ] && [ "$ELAPSED" -gt 60 ] && [ "$DONE" -gt 0 ]; then
    RATE=$(awk "BEGIN{printf \"%.1f\", $DONE*3600/$ELAPSED}")
    LEFT=$(( TOTAL - DONE ))
    ETAH=$(awk "BEGIN{printf \"%.1f\", $LEFT*$ELAPSED/($DONE*3600)}")
    echo " rate    : $RATE games/h over $(( ELAPSED / 60 )) min   ETA: ~${ETAH} h  ($LEFT left)"
    echo "           NOTE: early games are Isolation (fast). Rate will FALL as the"
    echo "           schedule reaches UTTT and Ataxx. Expect ~9.9 h total, not the"
    echo "           first-hour extrapolation."
fi
echo " last write to games.csv: ${AGE}s ago"
echo

# ---- verdicts -------------------------------------------------------
VERDICT="OK"
if [ "$DONE" -ge "$TOTAL" ]; then
    echo " >>> COMPLETE. All $TOTAL games present. Next step: run the analysis."
    echo "     python3 -m experiments.analyse --raw results/v2 \\"
echo "             --json results/v2/analysis.json --label v2-tournament"
echo "     python3 -m experiments.report --analysis results/v2/analysis.json \\"
echo "             --out results/v2/report.md --figures results/v2/figures \\"
echo "             --run-meta results/v2/run_meta.json"
    VERDICT="DONE"
elif [ "$STATE" = "failed" ]; then
    echo " >>> FAILED. The unit gave up (likely start-limit-hit: 5 crashes in 10 min)."
    echo "     Diagnose first:  tail -40 $LOG"
    echo "     Then resume   :  sudo systemctl reset-failed tournament && sudo systemctl start tournament"
    VERDICT="FAILED"
elif [ "$STATE" != "active" ]; then
    echo " >>> NOT RUNNING (state=$STATE). Start it:  sudo systemctl start tournament"
    VERDICT="STOPPED"
elif [ "$AGE" -gt 1800 ]; then
    echo " >>> STALLED. No completed game for ${AGE}s. Even the worst legal case"
    echo "     (Ataxx easy, 2 budgeted seats, 300-ply cap) is ~600s, so this is wrong."
    echo "     Restart is safe - resume is crash-safe:  sudo systemctl restart tournament"
    VERDICT="STALLED"
elif [ "$AGE" -gt 900 ]; then
    echo " >>> SLOW but probably fine. ${AGE}s since the last game. A long Ataxx-easy"
    echo "     game can legitimately take ~600s. Re-check in 10 min before acting."
    VERDICT="SLOW"
fi

if [ "$NRESTARTS" -gt 3 ] && [ "$VERDICT" != "DONE" ]; then
    echo " >>> RESTART LOOP WARNING: $NRESTARTS restarts. If the game count is NOT"
    echo "     rising between two checks, it is crashing on the same game every time."
    echo "     Capture evidence before restarting:  tail -60 $LOG"
fi
[ "$VERDICT" = "OK" ] && echo " >>> Healthy. Nothing to do."
echo

echo "--- last 6 log lines ---"
tail -6 "$LOG" 2>/dev/null || echo "(no log yet)"
