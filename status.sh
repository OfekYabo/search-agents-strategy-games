#!/bin/bash
# Tournament status. Designed to be run from the Windows host with:
#
#   multipass exec tournament -- /home/ubuntu/search-agents-strategy-games/status.sh
#
# Prints service state, progress toward 2160 games, throughput, ETA, and
# explicit STALL / RESTART-LOOP verdicts so no interpretation is needed.

DIR=/home/ubuntu/search-agents-strategy-games
RAW=$DIR/results/raw
LOG=$DIR/results/tournament.log
TOTAL=2160

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
    echo "           schedule reaches UTTT and Ataxx. Expect ~8.6 h total, not the"
    echo "           first-hour extrapolation."
fi
echo " last write to games.csv: ${AGE}s ago"
echo

# ---- verdicts -------------------------------------------------------
VERDICT="OK"
if [ "$DONE" -ge "$TOTAL" ]; then
    echo " >>> COMPLETE. All $TOTAL games present. Next step: run the analysis."
    echo "     python3 -m experiments.analyse --raw results/raw | tee results/tables.md"
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
