#!/bin/bash
# V2-vs-V3 duel suite. Same rules as run_v3_suite.sh:
# sequential, never parallel; a failing step does not stop the suite; the long
# step is unbounded because it is crash-safe and resumable.
DIR=/home/ubuntu/search-agents-strategy-games
cd "$DIR" || exit 1
SUITE_LOG="$DIR/results/duel/suite.log"
mkdir -p "$DIR/results/duel"

say() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$SUITE_LOG"; }

step() {
    local name="$1"; shift
    local limit="$1"; shift
    local started ended rc
    started=$(date +%s)
    say "START  $name (timeout: $limit)"
    if [ "$limit" = "none" ]; then "$@" >>"$SUITE_LOG" 2>&1; rc=$?
    else timeout --signal=TERM --kill-after=60 "$limit" "$@" >>"$SUITE_LOG" 2>&1; rc=$?; fi
    ended=$(date +%s)
    if [ "$rc" -eq 0 ]; then say "OK     $name in $(( (ended - started) / 60 )) min"
    elif [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
        say "TIMED OUT $name after $(( (ended - started) / 60 )) min - continuing"
    else say "FAILED $name rc=$rc after $(( (ended - started) / 60 )) min - continuing"; fi
    return 0
}

say "=================================================================="
say "V2-vs-V3 duel starting. 25 trials (~11 h), sequential, never parallel."
say "=================================================================="

# Unbounded: crash-safe and resumable, so running long always beats being
# killed partway.
step "duel/v2-vs-v3" none \
    python3 -m experiments.version_duel \
        --versions v2,v3 --trials 25 --out "$DIR/results/duel"

step "duel-report" 1800 \
    python3 -m experiments.duel_report \
        --raw "$DIR/results/duel" \
        --commentary "$DIR/docs/report/commentary-duel.md" \
        --figures "$DIR/results/duel/figures" \
        --out "$DIR/results/duel/report.md"

say "=================================================================="
say "Duel finished.  results/duel/report.md"
say "=================================================================="
