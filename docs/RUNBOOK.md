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

**13. Resume exists, is on by default, and is now crash-safe.** `completed_ids()` (`logger.py:78`) reads back
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
python3 -m unittest discover -s tests # expect 176 passing, ~21 s
```

> There is no `pytest` in this project and none is installed on the tournament VM.
> `python3 -m pytest` will fail with "No module named pytest" — that is expected, not a
> broken environment. The suite is stdlib `unittest`.

No `pip install`, no virtualenv, no environment variables. Output paths are CLI flags.

### Guest-side quiet hours

The runbook's "idle machine" requirement covers the **host**; the guest has its own noise.
Ubuntu ships timers that will run `apt` mid-decision during a 21-hour run:

```bash
sudo systemctl disable --now unattended-upgrades apt-daily.timer \
     apt-daily-upgrade.timer motd-news.timer
sudo systemctl mask systemd-tmpfiles-clean.timer
systemctl list-timers --all | head
```

### Python version

Development was **3.8.10**; Ubuntu 22.04 ships **3.10**. The code targets 3.8 syntax so it
runs unchanged, and a faster interpreter is **fair to all four agents** — it is not a
validity problem. But it does mean **more search per budget**, so the calibration numbers
from the development machine are not comparable to the host's. **Record the interpreter
version alongside the results**, and re-measure on the host (step 3 below).

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

   > **Check Isolation-hard specifically.** Its 0.02 s budget is the cell most exposed to
   > virtualization jitter — a hypervisor scheduling quantum of ~1 ms is 5% of that budget
   > before the algorithm does anything, and Alpha-Beta already measured **+18%** there on
   > near-bare WSL2. If it degrades badly under Multipass, that cell either moves elsewhere
   > or the limitation gets recorded. Do not silently accept it:
   > ```bash
   > python3 - <<'EOF'
   > import csv
   > G={r["game_id"]:(r["game"],float(r["time_budget_s"])) for r in csv.DictReader(open("results/smoke/games.csv"))}
   > x=[float(m["elapsed_s"])/G[m["game_id"]][1] for m in csv.DictReader(open("results/smoke/moves.csv"))
   >    if G[m["game_id"]][0]=="isolation" and m["agent"] in ("alpha_beta","mcts")]
   > print("isolation-hard: mean %.0f%% of budget, max %.0f%%" % (100*sum(x)/len(x), 100*max(x)))
   > EOF
   > ```

### Supervising the run

Because resume is crash-safe (Q13), a supervisor is now safe and makes the run self-healing
across a guest reboot. **This is the unit actually installed on the tournament VM** — see
"Operations log" below for why it differs from the first draft:

```ini
[Unit]
Description=Search-agents tournament v1 (full grid, 2160 games)
Documentation=file:///home/ubuntu/search-agents-strategy-games/docs/RUNBOOK.md
After=local-fs.target
StartLimitIntervalSec=600
StartLimitBurst=5

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/home/ubuntu/search-agents-strategy-games
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/python3 -m experiments.tournament --games all --configs all --trials 20 --out results/raw
Restart=on-failure
RestartSec=30
TimeoutStopSec=120
StandardOutput=append:/home/ubuntu/search-agents-strategy-games/results/tournament.log
StandardError=append:/home/ubuntu/search-agents-strategy-games/results/tournament.log

[Install]
WantedBy=multi-user.target
```

Resume is idempotent, so a restart re-reads `games.csv`, drops any orphan move rows from the
interrupted game, and continues. Take a VM snapshot **before** the calibration gate, so a
failed gate does not cost the setup.

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

---

## Operations log — tournament VM, 2026-08-07

Decisions taken while provisioning the dedicated Multipass VM (`tournament`, 4 vCPU /
4 GB, Ubuntu 22.04, **Python 3.10.12**), recorded here because several depart from the
draft above. Host is otherwise idle; all systemd timers disabled except a masked
`systemd-tmpfiles-clean.timer`.

### Corrections to the text above

| Was | Now | Why |
|---|---|---|
| "expect 168 passing" | **176 passing, 20.6 s** | Suite grew; two of the new tests are the MCTS-rollout guards below. |
| Dev machine Python 3.8.10 | VM runs **3.10.12** | Faster interpreter, fair to all four agents, but calibration numbers are host-specific (see "Python version" above). |

### MCTS rollout parameters — verified, not assumed

`tournament.py:43` pins `MCTS_ROLLOUT = {"epsilon": 1.0, "sample_k": 1, "rollout_depth": 10}`.
Confirmed against `results/calibration.txt:72-94`: `eps1.00 k1 D10` is the **only**
configuration that scores top on all three games (isolation 1.00, uttt 1.00, ataxx 0.38).
`eps1.00 k1 D400` ties on the first two but collapses to 0.00 on Ataxx at 1.2 sims/root, so
the `D10` truncation is load-bearing.

Verified the values reach the constructor rather than being shadowed: `tournament.py:101-102`
passes `**MCTS_ROLLOUT` as keywords over the guided defaults at `mcts_agent.py:49-50`, and
`mcts_agent.py:90-91` reads those closure parameters directly. Nothing rebinds them between.
Proved at runtime by spying on `mcts_agent.make` — captured exactly
`{'max_nodes': 50000, 'epsilon': 1.0, 'sample_k': 1, 'rollout_depth': 10}` with no
positional arguments (which would otherwise bind to `exploration`).

**Effect on the measurement** (median simulations per decision, hard config):

| Game | before (defaults) | after | factor | sims per root move |
|---|---|---|---|---|
| ataxx | 28 | 262 | 9.4x | 0.6 → **13.7** |
| isolation | 460 | 843 | 1.8x | 104.2 → **240.9** |
| uttt | 15 | 570 | **38.0x** | 2.0 → **73.5** |

Ataxx MCTS is still below one simulation per candidate at hard (13.7 against mean branching
~51). Finding #1 stands — this is a real result about MCTS on high-branching games, not a
configuration error — but report the **post-fix** number, not the 0.6.

### Overshoot after the rollout change — no regression

Two full smoke runs (`results/smoke2`, `results/smoke3`; all games, hard, 2 trials).
The first showed alarming maxima (ataxx/mcts +22.6%, isolation/mcts +12.8%, uttt/mcts
+11.3%). **These are host jitter, not the rollout change:**

1. They did not reproduce — smoke3's worst move across all 1176 budgeted decisions is +7.3%,
   everything else ≤ +3.4%, and the outliers landed on entirely different plies.
2. p99 is ≤ 101% for every MCTS cell in both runs, and the mean is 100.1-100.2% — identical
   to the pre-fix smoke (100.1 / 100.3 / 100.5).
3. Anti-correlated with the obvious mechanism: the worst outlier was ataxx/mcts at **ply 3
   with 139 simulations** — a tiny tree. Cost growth from larger trees would appear at late
   plies, not early ones.

Both smoke runs: 72 games, 0 `illegal_move`, 0 `agent_error`, 0 orphan move rows, 0
duplicate `(game_id, ply)`, and column discipline intact (`nodes` for Alpha-Beta only,
`simulations` for MCTS only).

> Both smoke runs executed **with VS Code and an active agent session running on the VM**.
> Steady-state that costs ~3% CPU aggregate, but the extension host bursts, and on
> isolation-hard a 4 ms spike is 20% of the 0.02 s budget. Close VS Code before the real run.

### Mid-write kill test — the gate for `Restart=on-failure`

Passed, but note that the **single-kill version of this test is close to worthless**. Move
rows are written and flushed *before* the games row, which acts as the commit marker
(`logger.py:104-113`), so orphans only exist in a narrow window between the two flushes. A
single kill usually misses it and reports a clean `dupes: 0` without ever executing
`_drop_orphan_moves`. That is exactly what happened on the first attempt here.

Three tests were run; all three must pass before trusting a supervisor:

1. **Prescribed test** — kill -9 at 25 s, then resume. Result: 24/24 games, `dupes: 0`,
   0 orphans. But 0 orphans existed at kill time, so the fix was never exercised.
2. **Forced orphan path** — dropped the last games row while keeping its 28 move rows, and
   appended a truncated final line to mimic a kill mid-`write`. Resume dropped all 29 rows,
   replayed the game, and produced `dupes: 0`, 0 orphans, 24/24 games, with the replayed
   game internally consistent (12 plies / 12 move rows / `end_reason=eliminated`).
3. **Restart loop** — nine consecutive SIGKILLs at 4, 9, 6, 13, 7, 11, 5, 17, 8 s, each
   followed by resume. Progress monotonic across every restart; final state `dupes: 0`,
   0 duplicate games rows, 0 orphans, 24/24 games, and `games.plies == count(move rows)` for
   every game.

Test 3 is the one that licenses `Restart=on-failure`, because it is what the supervisor
actually does.

### Unit file — what changed from the draft and why

| Change | Reason |
|---|---|
| `After=local-fs.target` (was `network.target`) | The run needs no network. Waiting on it only adds a boot-time failure mode. |
| `Environment=PYTHONUNBUFFERED=1` | `tournament.py:136-138` flushes its progress lines but not the header/footer. Without this the log can read stale during monitoring. |
| `StandardOutput/Error=append:results/tournament.log` | A real file that survives reboot, so monitoring never depends on journald retention. Needs systemd ≥ 240; VM has 249. |
| `TimeoutStopSec=120` | Bounded clean stop. |
| **`StartLimitIntervalSec=600` + `StartLimitBurst=5`** | See below. |

**`StartLimitBurst=5` — the one real judgement call.** Resume makes an ordinary restart
productive, so a transient crash self-heals. But a *deterministic* crash on one specific game
would restart forever making zero progress, and the operator is expected to be away for the
whole run. With this limit, five crashes inside ten minutes stop the unit and leave the
evidence in place instead of burning hours in a silent loop.

The trade-off is real and was accepted deliberately: if the limit trips at hour 2, the run
sits idle until someone returns. Removing the limit means it instead *spins* uselessly for
those same hours — the same wall-clock lost, but a much harder state to diagnose. A stopped
unit with `Result=start-limit-hit` is unambiguous. Clear it with:

```bash
sudo systemctl reset-failed tournament && sudo systemctl start tournament
```

**Deliberately NOT set: `Nice=`, `CPUSchedulingPolicy=`, `CPUAffinity=`.** Raising priority
is tempting for timing purity, but calibration and both smoke runs ran at default priority.
Changing scheduling now would make the tournament's timings incomparable to the calibration
that selected its hyperparameters — a methodological change disguised as an ops tweak.
