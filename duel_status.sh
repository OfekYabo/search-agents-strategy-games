#!/bin/bash
# V2-vs-V3 duel status, for the Windows host:
#
#   multipass exec tournament -- /home/ubuntu/search-agents-strategy-games/duel_status.sh
#
# Separate from status.sh because the duel has its own schema, its own total
# and its own unit. Mixing them would make one of the two counts silently wrong.

DIR=/home/ubuntu/search-agents-strategy-games
RAW=$DIR/results/duel
LOG=$RAW/suite.log
EXPECT_VERSIONS="v2,v3"

# 3 agents x 3 games x 3 configs x trials x 2 seat orders.
TRIALS=$(sed -n 's/.*--trials \([0-9]*\).*/\1/p' "$DIR/run_duel_suite.sh" | head -1)
[ -z "$TRIALS" ] && TRIALS=25
TOTAL=$(( 3 * 3 * 3 * TRIALS * 2 ))

if [ -f "$RAW/games.csv" ]; then
    DONE=$(( $(wc -l < "$RAW/games.csv") - 1 ))
    AGE=$(( $(date +%s) - $(stat -c %Y "$RAW/games.csv") ))
else
    DONE=0; AGE=-1
fi
[ "$DONE" -lt 0 ] && DONE=0

STATE=$(systemctl is-active duel-suite)
RESULT=$(systemctl show duel-suite -p Result --value)
START=$(systemctl show duel-suite -p ExecMainStartTimestamp --value)

echo "=============================================================="
echo " V2-vs-V3 DUEL STATUS        $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "=============================================================="
echo " service : $STATE   result: $RESULT"
echo " started : $START"

# Which versions are actually being played? Read the script and the data, the
# same three-source check status.sh uses - running the wrong pair would waste
# the night exactly like running the wrong version would.
SCRIPT_V=$(sed -n 's/.*--versions \([^ ]*\).*/\1/p' "$DIR/run_duel_suite.sh" | head -1)
DATA_V="-"
if [ -f "$RAW/games.csv" ]; then
    DATA_V=$(python3 -c "
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
seen = sorted({r['first_version'] for r in rows} | {r['second_version'] for r in rows})
print(','.join(seen) if seen else '-')" "$RAW/games.csv" 2>/dev/null || echo "?")
fi
echo " versions: script=$SCRIPT_V  in data=$DATA_V   (expect $EXPECT_VERSIONS)"
echo " trials  : $TRIALS   output: $RAW"
if [ "$SCRIPT_V" != "$EXPECT_VERSIONS" ] || \
   { [ "$DATA_V" != "-" ] && [ "$DATA_V" != "$EXPECT_VERSIONS" ]; }; then
    echo
    echo " >>> WRONG VERSION PAIR. Stop before spending the night on it:"
    echo "       sudo systemctl stop duel-suite"
    echo "     Check --versions in run_duel_suite.sh, then delete $RAW"
    echo "     before restarting - a resume would keep the wrong games."
fi
echo " load    :$(cut -d' ' -f1-3 /proc/loadavg | sed 's/^/ /')"
echo

PCT=$(awk "BEGIN{printf \"%.1f\", 100*$DONE/$TOTAL}")
echo " progress: $DONE / $TOTAL games  (${PCT}%)"
FILLED=$(awk "BEGIN{printf \"%d\", 50*$DONE/$TOTAL}")
printf " ["
for i in $(seq 1 50); do [ "$i" -le "$FILLED" ] && printf "#" || printf "."; done
printf "]\n"

SEC=$(systemctl show duel-suite -p ExecMainStartTimestampMonotonic --value)
NOW=$(awk '{printf "%d", $1*1000000}' /proc/uptime)
ELAPSED=$(( (NOW - SEC) / 1000000 ))
if [ "$STATE" = "active" ] && [ "$ELAPSED" -gt 300 ] && [ "$DONE" -gt 0 ]; then
    LEFT=$(( TOTAL - DONE ))
    ETAH=$(awk "BEGIN{printf \"%.1f\", $LEFT*$ELAPSED/($DONE*3600)}")
    echo " rate    : $(awk "BEGIN{printf \"%.1f\", $DONE*3600/$ELAPSED}") games/h  ETA ~${ETAH} h ($LEFT left)"
    echo "           NOTE: cells are interleaved by trial, so the rate is"
    echo "           representative from early on - unlike the main grid."
fi
echo " last write: ${AGE}s ago"
echo

if [ "$DONE" -ge "$TOTAL" ]; then
    echo " >>> COMPLETE. Check for results/duel/report.md"
elif [ "$STATE" = "failed" ]; then
    echo " >>> FAILED. Diagnose:  tail -40 $LOG"
    echo "     Then: sudo systemctl reset-failed duel-suite && sudo systemctl start duel-suite"
elif [ "$STATE" != "active" ]; then
    echo " >>> NOT RUNNING. Start it:  sudo systemctl start duel-suite"
elif [ "$AGE" -gt 1800 ]; then
    echo " >>> STALLED. Restart is safe - the duel resumes by game_id:"
    echo "     sudo systemctl restart duel-suite"
else
    echo " >>> Healthy. Nothing to do."
fi
echo
echo "--- suite steps ---"
if [ -f "$LOG" ]; then
    grep -E "START |OK    |FAILED|TIMED OUT|finished" "$LOG" | tail -8
else
    echo "(not started yet)"
fi
echo
if [ -f "$RAW/report.md" ]; then echo "  [ready] results/duel/report.md"
else echo "  [ ... ] results/duel/report.md"; fi
