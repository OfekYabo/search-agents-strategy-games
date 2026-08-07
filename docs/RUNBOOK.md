# Runbook: provisioning and running the tournament

Answers to the provisioning questions, from the code. Every claim cites `file:line`
or a measurement taken on the development machine (Intel i7-1165G7, 2 cores and 3 GB
visible to WSL2, Python 3.8.10).

---

## Runtime and parallelism

**1. Language, runtime, threading model.**
Python **3.8.10**, **standard library only** — there is no `requirements.txt` and none is
needed. Verified: no `threading`, `multiprocessing`, or `concurrent.futures` import
exists anywhere outside tests. The search is **single-threaded, single-process**, so the
GIL is irrelevant — nothing contends for it.

**2. Concurrency in the harness — read this one carefully.**
**The harness is strictly sequential.** `experiments/tournament.py:96` is a plain
`for index, cell in enumerate(schedule)` loop that plays one game to completion before
starting the next.

> **`--workers` does not parallelise anything.** It is accepted at
> `experiments/tournament.py:131`, passed through `run()` at `:88`, and handed to
> `runner.play_game(..., workers=workers)` at `:115` **solely so it can be recorded in
> the `workers` column of `games.csv`**. Setting `--workers 8` will not use 8 cores; it
> will change one CSV column. Do not rely on it.

**3. Agent-internal parallelism.** None. Alpha-Beta is a single recursive negamax
(`agents/alpha_beta_agent.py`); MCTS is a single-threaded UCT loop
(`agents/mcts_agent.py:68`). No root, leaf, or tree parallelism.

**4. Peak process and thread count.** **One process, one thread.** Peak RSS measured at
**12 MB** for the worst case (see Q11).

---

## Time-budget correctness

**5. Clock.** `time.monotonic`, defaulted at `agents/base.py:63` and `:124`. Wall clock,
not CPU time — deliberately, because the study compares two paradigms under a *realistic*
shared budget, and CPU time would let a descheduled process claim time it did not have.

**6. What the budget includes.** The timer starts when `SearchContext` is constructed
inside `decide()` and stops when the agent returns, so it covers **everything the agent
does**: move generation, state construction, evaluation, table lookups. It excludes the
runner's own bookkeeping — the legality check and CSV write happen after `elapsed_s` is
captured, so validation is never charged to the agent.

**7. Cutoff behaviour and measured overshoot.** There is no mid-operation abort, but every
agent is interruptible at a fine granularity:

| Agent | Polls at | Interval |
|---|---|---|
| Alpha-Beta | every node | `set_check_every(16)`, `alpha_beta_agent.py:85` |
| MCTS | every simulation **and inside each rollout ply** | `set_check_every(1)`, `mcts_agent.py:63`; in-rollout stop at `:147` |
| Heuristic | every candidate move | `set_check_every(1)`, `heuristic_agent.py:18` |

Alpha-Beta additionally **discards a partially completed deepening iteration entirely** —
the returned move always comes from the last fully completed depth.

**Measured overshoot over 72 real games** (maximum, not mean):

| Game | Alpha-Beta | MCTS |
|---|---|---|
| Isolation (0.02 s) | +18% | +1% |
| UTTT (0.1 s) | +10% | +7% |
| Ataxx (0.1 s) | +1% | +10% |

> Both figures were far worse before a smoke test caught them: Alpha-Beta was **+85%** on
> UTTT (polling every 512 nodes when it only expands ~1,500 per decision) and MCTS **+35%**
> (a 25.8 ms rollout that could not be interrupted). Fixed in commit `f790935`.

**8. Load and frequency sensitivity — yes, and it is unavoidable.**
Because the budget is wall clock, **how much search a budget buys depends on the machine
and on what else it is doing.** A single Alpha-Beta decision on Ataxx was observed at
0.290 s against a 0.1 s budget when the test suite ran concurrently; 60 successive
decisions on an idle machine gave a maximum of 0.1017 s (+1.7%).

**Consequences for provisioning:**
- **Run on an otherwise idle machine.** Nothing else scheduled, no backups, no updates.
- Trials are **interleaved across matchups** (`tournament.py:78`) precisely so that thermal
  drift reaches every agent equally instead of accumulating against whichever ran last.
- Re-running an identical seed need not reproduce a game. See Q16.

---

## Scale and duration

**9. Tournament structure.**
- **4 agents**: `random`, `heuristic`, `alpha_beta`, `mcts` (`tournament.py:23`)
- **6 unordered pairings**, each played in **both seat orders** = **12 directed matchups**
  (`pairings()`, `:34`). First-player swap is built into the pairing list, not applied
  per trial.
- **3 games** x **3 configs** x **T trials**, default `T=20`
- Grid = `3 x 12 x 3 x 20` = **2,160 games**

Budgets (**easy means MORE time; hard means LESS** — easy to read backwards),
`calibrate.py:148`:

| Game | easy | main | hard |
|---|---|---|---|
| Isolation | 0.5 s | 0.1 s | 0.02 s |
| Ataxx | 2.0 s | 0.5 s | 0.1 s |
| UTTT | 2.0 s | 0.5 s | 0.1 s |

**10. Total moves and wall clock, with arithmetic.**

Measured mean game lengths: Isolation **15.9** plies, UTTT **59.5**, Ataxx **182.6**.

Of the 6 pairings, one uses no search time (`random` vs `heuristic`), four use one seat,
and one uses two — averaging **1.0 budgeted seat per game**, so **half of all plies consume
budget**.

Per config, per game: `12 matchups x 20 trials = 240 games`.

| Game | Moves/config | Budgeted/config | easy | main | hard | subtotal |
|---|---|---|---|---|---|---|
| Isolation | 3,816 | 1,908 | 954 s | 191 s | 38 s | **20 min** |
| UTTT | 14,280 | 7,140 | 14,280 s | 3,570 s | 714 s | **5.2 h** |
| Ataxx | 43,824 | 21,912 | 43,824 s | 10,956 s | 2,191 s | **15.8 h** |
| **Total** | **185,760 move rows** | | | | | **≈ 21 h** |

**Ataxx-easy alone is 12.2 h — 58% of the entire run.**

> These are timings for the development machine. Since the run is **single-threaded**,
> only **single-core** performance matters; 10 cores will not make it faster on their own.
> Re-measure on the target host before committing (see "Before you start", step 3).

**11. Peak memory.** Measured on the worst case — MCTS on Ataxx at a 2.0 s budget, the
largest tree the grid produces: **12 MB peak RSS, 302 simulations**. The tree cannot exceed
`max_nodes = 50,000` by construction (`tournament.py:26`), and Alpha-Beta's table cannot
exceed `max_entries = 200,000`. **2 GB is ample; 4 GB is generous.**

---

## Durability

**12. Writes are incremental.** `GameLogger.write()` appends one `games.csv` row plus one
`moves.csv` row per move and calls `flush()` on both handles **after every game**
(`logger.py:75-76`). Files are opened in append mode (`:36-37`). A kill at hour 20 loses at
most the game in flight.

**13. Resume exists and is used by default.** `completed_ids()` (`logger.py:78`) reads back
every `game_id` already in `games.csv`; `run()` skips those (`tournament.py:109`). Disable
with `--no-resume`. The id comes from **one shared function**, `runner.game_id`
(`runner.py:53`), called by both the runner and the tournament precisely so the two cannot
desync — a duplicated format would silently make resume re-run completed games with no
error.

**14. Log volume.** Measured at **120 B per game row** and **74 B per move row**. Full grid:
`2,160 x 120 + 185,760 x 74` ≈ **14 MB**. Not a constraint.

---

## Reproducibility

**15. Seeding.** One seed per game, derived deterministically from
`(game, agent_first, agent_second, config, trial)` via **SHA-256**, not `hash()`
(`runner.py:44-51`) — Python salts `hash()` per process, which would make every logged game
irreproducible across runs. That single seed drives one `random.Random` threaded through
the whole game, so both agents draw from the same stream in a fixed order.

**16. Nondeterminism — one source, and it is intrinsic.**
The seed makes every *random choice* reproducible: the random agent's picks, the heuristic
agent's tie-breaks, MCTS expansion order and rollouts. It does **not** make a
wall-clock-budgeted search bit-reproducible, because how many nodes Alpha-Beta expands
depends on how fast the machine was for those milliseconds.

Observed directly: Alpha-Beta versus the heuristic agent over the same 20 seeds at a 50 ms
budget scored **20/20 in one run and 18/20 in another** — same code, same seeds.

This is the price of using wall clock as the budget, which is the only unit that is fair
across two different search paradigms. Consequences: **the CSV is one sample, not a
replayable artifact**, and reported figures need confidence intervals rather than bare
percentages. Only `random` and `heuristic` are genuinely bit-reproducible.

---

## To run it

**17. Repository, branch, and commands.**

```bash
git clone https://github.com/OfekYabo/search-agents-strategy-games.git
cd search-agents-strategy-games
git checkout plan-refinement          # all work lives here; main is the baseline only
python3 --version                     # 3.8+ required; no other dependencies
python3 -m unittest discover -s tests # expect 168 passing, ~25 s
```

No `pip install`, no virtualenv, no environment variables. Output paths are CLI flags.

### Before you start the long run

1. **Provision**: 2 dedicated vCPU is enough (the run uses one); 4 GB RAM is generous.
   The value of a 10-core host here is **isolation, not speed** — leave the other cores
   free so nothing steals time mid-decision.
2. **Confirm the machine is idle.** No updates, backups, indexing, or other VMs.
3. **Re-measure the budget curve on this host** (~2 min) — the sims-per-root-move and
   Alpha-Beta-depth figures in `PLAN.md` were measured elsewhere and are machine-dependent:
   ```bash
   python3 -m experiments.measure_branching     # ~3 min, validates the move generators
   ```
4. **Run the calibration** (~1 h). Phase 0 is a **gate**: if any agent overruns its budget,
   stop, because every later number would be measuring the wrong thing.
   ```bash
   python3 -m experiments.calibrate | tee results/calibration.txt
   ```
5. **Run the pipeline smoke test** (~2 min). Cheap insurance on a new host.
   ```bash
   python3 -m experiments.tournament --games all --configs hard --trials 2 --out results/smoke
   ```
   Expect 72 rows, **zero** `illegal_move` or `agent_error`, `nodes` populated for
   Alpha-Beta and empty for MCTS with `simulations` the reverse, and per-move `elapsed_s`
   at or under budget.

### The run

```bash
git tag v1-tournament                 # so v1 stays reproducible for the v1-vs-v2 comparison
nohup python3 -m experiments.tournament \
      --games all --configs all --trials 20 --out results/raw \
      > results/tournament.log 2>&1 &
```

Safe to interrupt — re-issuing the same command resumes from `results/raw/games.csv`.

```bash
python3 -m experiments.analyse --raw results/raw | tee results/tables.md
```

### If you want it faster than 21 hours

The harness will not do it for you — `--workers` is inert (Q2). The only way is **several
processes with disjoint schedules writing to separate output directories**, merged
afterwards. Ataxx-easy is 12.2 h of the 21 h, so splitting *that cell* by trial range is
where the gain is.

**This is a methodological change, not just an operations one.** Parallel processes share
L3 cache and memory bandwidth, which perturbs the very quantity being measured.
`docs/spec/technical-spec.md` §7.4 requires that if it is done, the worker count is recorded
and **the per-move timing distribution is compared against a sequential run** — if it shifts,
the parallel results are not comparable and the run must be sequential. Budget on the order
of an hour to validate that before trusting a parallel run.
