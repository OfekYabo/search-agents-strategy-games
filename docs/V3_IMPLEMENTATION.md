# V3 implementation summary

V3 is the next experimental version after the frozen V2 tournament. V1 and V2
agent/evaluator directories are intentionally unchanged.

## Selected changes

- **Ataxx evaluator:** same material/exposure features, reweighted from 70/30 to
  **47/53**. No extra feature-computation cost is introduced.
- **MCTS subtree reuse:** the branch selected on the previous turn is retained;
  after the opponent replies, an already-expanded matching child is re-rooted
  and its visit/value statistics are reused.
- **Independent V3 RNG streams:** each seat gets a deterministic RNG stream
  derived from the game seed. V1/V2 keep their historical shared-RNG behaviour.
- **Bounded-memory instrumentation:** move logs now include Alpha-Beta TT
  lookups/hits/occupancy and MCTS active/reused tree-node counts.
- **Duplicate legal-move removal:** hot Alpha-Beta/MCTS/runner paths reuse a
  single legal-move list for terminal detection and subsequent processing.
- **Sequential tournament enforcement:** `--workers` remains accepted for CLI
  compatibility but values other than 1 are rejected. Time-limited searches are
  not run concurrently.
- **Version-owned caps:** V2/V3 tournament rows take caps from the selected agent
  package rather than the historical V1 constants in the harness.

## Optional asymmetric-time self-play

This is deliberately separate from the main round-robin and runs only when
invoked explicitly:

```bash
python -m experiments.time_budget_selfplay \
  --game ataxx \
  --agent mcts \
  --budgets 0.1,0.5,2.0 \
  --trials 10 \
  --out results/time-selfplay/ataxx-mcts
```

The same command supports `--agent alpha_beta`. For every unordered pair of
budgets it runs both seat orders with the same base seed and independent
per-seat RNG streams.

## Validation performed before packaging

- Main V3 smoke grid: Isolation/hard, 1 trial, all 12 directed matchups — no
  illegal moves or agent errors.
- Optional time-selfplay smoke: MCTS 0.002 s vs 0.004 s — both seat orders
  completed and wrote independent CSVs.
- Unit tests were run in split suites because the complete discovery run exceeds
  the execution sandbox's single-command timeout. Collectively all discovered
  test modules passed after the change; the test loader currently discovers 273
  tests.

## Small performance checks

These are engineering smoke benchmarks, not final experimental results.

- 500 identical Isolation MCTS rollouts: legal-move calls dropped by ~49.9%.
- Fresh Isolation MCTS decisions at 0.02 s: median simulations increased from
  354.5 (V2) to 462.5 (V3), about +30% in that run.
- Fixed-depth Alpha-Beta with the same evaluator and same explored-node count:
  search time decreased by ~8% on Isolation depth 5 and ~16% on Ataxx depth 3.
- Ataxx one-ply V3 evaluator vs V2 evaluator: 13-7 over 20 seat-balanced
  screening games (65% score for V3).

The full V3 tournament must still be rerun from scratch before using V3 numbers
in the paper, because RNG streams, Ataxx evaluation, MCTS search state, and
search throughput all changed.

## Minor analysis additions before the full V3 run

The final V3 logging/analysis pass adds no extra search work. `legal_move_count`
was already recorded at each decision, so the analysis now reports observed
branching factor (mean, median, p95) from positions reached in the actual
tournament. It also derives Alpha-Beta nodes/second and MCTS simulations/second
from the existing work counters and elapsed time. MCTS tree-reuse statistics
are summarised from the counters already introduced for V3.

Game rows carry an `experiment` label (`main_tournament`), while the optional
asymmetric-time experiment writes `time_selfplay`. This is metadata only and
does not alter game ids, seeds, agent behavior, or the main tournament grid.
