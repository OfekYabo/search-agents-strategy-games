#!/bin/bash
# V3 experiment suite: runs every experiment sequentially, unattended.
#
#   sudo systemctl start v3-suite
#
# Design rules, all deliberate:
#
#   NEVER PARALLEL. The budget is wall clock, so two experiments running at
#   once would each steal search time from the other and both results would be
#   measuring contention rather than the algorithms. `set -e` is NOT used and
#   nothing is backgrounded.
#
#   A FAILING STEP MUST NOT STOP THE SUITE. Each step is wrapped so a crash,
#   a non-zero exit, or a timeout is recorded and the next step still starts.
#   The main grid is the deliverable; an optional experiment dying must never
#   cost it.
#
#   EVERY STEP IS BOUNDED except the main grid. A crash is survivable, but a
#   HANG would silently eat the whole night, and `|| true` does not protect
#   against that - only a timeout does. The main grid is deliberately
#   unbounded: it is crash-safe and resumable, so letting it run long is
#   always better than killing it partway.
#
# Order: fastest first, main grid last. See ORDER note below.

DIR=/home/ubuntu/search-agents-strategy-games
cd "$DIR" || exit 1

SUITE_LOG="$DIR/results/v3/suite.log"
mkdir -p "$DIR/results/v3"

say() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$SUITE_LOG"; }

# step <name> <timeout-seconds|none> <command...>
step() {
    local name="$1"; shift
    local limit="$1"; shift
    local started ended rc
    started=$(date +%s)
    say "START  $name (timeout: $limit)"
    if [ "$limit" = "none" ]; then
        "$@" >>"$SUITE_LOG" 2>&1
        rc=$?
    else
        timeout --signal=TERM --kill-after=60 "$limit" "$@" >>"$SUITE_LOG" 2>&1
        rc=$?
    fi
    ended=$(date +%s)
    if [ "$rc" -eq 0 ]; then
        say "OK     $name in $(( (ended - started) / 60 )) min"
    elif [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
        say "TIMED OUT $name after $(( (ended - started) / 60 )) min - continuing"
    else
        say "FAILED $name rc=$rc after $(( (ended - started) / 60 )) min - continuing"
    fi
    return 0
}

say "=================================================================="
say "V3 suite starting. Agent version v3. Sequential, never parallel."
say "=================================================================="

# ---------------------------------------------------------------- fast first
# Optional asymmetric-time self-play. Not crash-safe by design: it truncates
# its CSVs on start and has no resume, so a failure means re-running it, which
# is cheap. Bounded so a hang cannot delay the main grid indefinitely.
step "time-selfplay/mcts" 7200 \
    python3 -m experiments.time_budget_selfplay \
        --game all --agent mcts --budgets 0.1,0.5,2.0 --trials 10 \
        --out "$DIR/results/v3/time-selfplay-mcts"

step "time-selfplay/alpha_beta" 7200 \
    python3 -m experiments.time_budget_selfplay \
        --game all --agent alpha_beta --budgets 0.1,0.5,2.0 --trials 10 \
        --out "$DIR/results/v3/time-selfplay-alpha_beta"

# ---------------------------------------------------------------- long last
# The main V3 grid: 2700 games, the deliverable. Unbounded and resumable - a
# restart re-reads games.csv and continues, so it is safe to leave running.
step "main-grid/v3" none \
    python3 -m experiments.tournament \
        --games all --configs all --trials 25 \
        --agent-version v3 --out "$DIR/results/v3/raw"

# ---------------------------------------------------------------- analysis
# Cheap, and means a finished suite already has a readable report waiting.
step "analyse/v3" 1800 \
    bash -c "python3 -m experiments.analyse --raw '$DIR/results/v3/raw' \
        --json '$DIR/results/v3/analysis.json' --label v3-tournament \
        > '$DIR/results/v3/tables.md'"

step "report/v3" 1800 \
    python3 -m experiments.report \
        --analysis "$DIR/results/v3/analysis.json" \
        --out "$DIR/results/v3/report.md" \
        --figures "$DIR/results/v3/figures" \
        --commentary "$DIR/docs/report/commentary-v3.md" \
        --run-meta "$DIR/results/v3/raw/run_meta.json"

say "=================================================================="
say "V3 suite finished."
say "=================================================================="
