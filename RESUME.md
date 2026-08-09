# RESUME — read this first

You are picking this up after a gap, probably with no agent available.
Everything you need is on this page. `docs/RUNBOOK.md` has the reasoning;
this page has the actions.

**Date set up:** 2026-08-07 · **VM:** Multipass `tournament` (4 vCPU / 4 GB,
Ubuntu 22.04, Python 3.10.12) · **Branch:** `plan-refinement` · **Tag:** `v1-tournament`

---

## 1. The one command that matters

From **Windows PowerShell**, no SSH, no VS Code:

```powershell
multipass exec tournament -- /home/ubuntu/search-agents-strategy-games/status.sh
```

That prints service state, progress toward 2160 games, throughput, ETA, and an
explicit verdict line beginning `>>>`. **Read the `>>>` line — it tells you what
to do.** You do not need to interpret anything else on the page.

---

## 2. What is running

A systemd service called `tournament`, owned by PID 1 — **not** by your shell.
It survives SSH disconnect, VS Code closing, and VM reboot (it is `enabled`).

```
ExecStart=/usr/bin/python3 -m experiments.tournament \
          --games all --configs all --trials 20 --out results/raw
```

- **Grid:** 3 games x 12 directed matchups x 3 configs x 20 trials = **2160 games**
- **Expected duration:** **~8.6 h** (Isolation 0.24 h, UTTT 3.71 h, Ataxx 3.85 h)
- **Output:** `results/raw/games.csv`, `results/raw/moves.csv`
- **Log:** `results/tournament.log`
- **Unit file:** `/etc/systemd/system/tournament.service`

> **The 21 h figure in older notes is wrong.** It used random self-play game
> lengths (182.6 plies on Ataxx); real agent play is 45.0 plies. 8.6 h is correct.

### If it was never started

```powershell
multipass exec tournament -- sudo systemctl start tournament
```

The service is installed and enabled but was deliberately left **stopped** at
setup time, so the run would begin on a quiet machine rather than one with VS
Code loaded. If `status.sh` says `NOT RUNNING` and progress is `0 / 2160`, this
is the command you want.

---

## 3. Checking progress

```powershell
# full status (use this)
multipass exec tournament -- /home/ubuntu/search-agents-strategy-games/status.sh

# bare game count, if you want just a number
multipass exec tournament -- bash -c "wc -l < search-agents-strategy-games/results/raw/games.csv"

# live log tail
multipass exec tournament -- tail -20 /home/ubuntu/search-agents-strategy-games/results/tournament.log

# watch it refresh every 60 s (Ctrl-C to stop; safe, read-only)
while ($true) { clear; multipass exec tournament -- /home/ubuntu/search-agents-strategy-games/status.sh; sleep 60 }
```

**Read the rate figure with care.** The schedule runs Isolation first, which is
fast, so the first hour extrapolates to a wildly optimistic ETA (~1.4 h). The
rate will *fall* as the schedule reaches UTTT and then Ataxx. Trust ~8.6 h.

---

## 4. Stop / restart

```powershell
multipass exec tournament -- sudo systemctl stop tournament      # pause
multipass exec tournament -- sudo systemctl start tournament     # continue
multipass exec tournament -- sudo systemctl restart tournament   # stop+start
```

**Stopping and restarting is safe, at any time, including mid-game.** Resume is
crash-safe and was verified on this host with nine consecutive SIGKILLs plus a
forced-orphan-injection test: zero duplicate `(game_id, ply)` rows, zero orphan
move rows, monotonic progress across every restart. You lose at most the single
game in flight.

Do **not** add `--no-resume`. That would discard everything already played.

---

## 5. If it dies

Run `status.sh` first. It prints one of these:

| Verdict | Meaning | Do this |
|---|---|---|
| `Healthy` | Running normally | Nothing |
| `NOT RUNNING` | Stopped cleanly, never started, or someone stopped it | `sudo systemctl start tournament` |
| `SLOW` | No game finished for 15+ min | Wait 10 min and re-check. A long Ataxx-easy game legitimately takes ~600 s |
| `STALLED` | No game finished for 30+ min | `sudo systemctl restart tournament` |
| `FAILED` | Crashed 5x in 10 min, systemd gave up | See below |
| `COMPLETE` | All 2160 present | Go to section 6 |
| `RESTART LOOP WARNING` | 3+ restarts | Check whether the game count is *rising* between two checks |

### On `FAILED`

The unit has `StartLimitBurst=5` / `StartLimitIntervalSec=600`: five crashes
inside ten minutes and systemd stops trying. This is deliberate — a
*deterministic* crash on one specific game would otherwise spin forever while
you were away, and a stopped unit with `Result=start-limit-hit` is far easier to
diagnose than a silent loop. **Capture the evidence before restarting:**

```powershell
multipass exec tournament -- tail -60 /home/ubuntu/search-agents-strategy-games/results/tournament.log
multipass exec tournament -- sudo journalctl -u tournament -n 100 --no-pager
```

Then clear the limit and continue:

```powershell
multipass exec tournament -- sudo systemctl reset-failed tournament
multipass exec tournament -- sudo systemctl start tournament
```

### Telling a real loop from normal restarts

Run `status.sh` twice, ten minutes apart, and compare the **game count**.

- Count rising → it is making progress. Leave it alone even if restarts are nonzero.
- Count identical and restarts climbing → it is crashing on the same game every
  time. Do not just restart it; read the log first.

### If the VM itself is gone

```powershell
multipass list
multipass start tournament     # the service is `enabled`, so it auto-resumes on boot
```

---

## 6. When it finishes

`status.sh` prints `COMPLETE` at 2160/2160. Then:

```powershell
multipass exec tournament -- bash -c "cd search-agents-strategy-games && python3 -m experiments.analyse --raw results/raw | tee results/tables.md"
```

Then generate the report — tables, figures and all:

```bash
python3 -m experiments.analyse --raw results/raw \
        --json results/analysis.json --label <tag>
python3 -m experiments.report --analysis results/analysis.json
```

This needs `matplotlib` and `numpy` (`requirements-analysis.txt`), which the
tournament itself does not. Output is `results/report.md` plus
`results/figures/*.svg`, byte-identical for identical input.

**Interpretation goes in `docs/report/commentary.md`, never in
`results/report.md`** — the report is regenerated from scratch every time and any
edit to it is lost. Unfilled sections render as visible `[COMMENTARY NEEDED: id]`
callouts, so gaps are obvious rather than silent.

For a new run, write `results/raw/run_meta.json` (rollout parameters, interpreter,
host) or section 2 will correctly report that the metadata was not recorded.

Copy the results back to the host before deleting anything:

```powershell
multipass transfer tournament:/home/ubuntu/search-agents-strategy-games/results/raw/games.csv .
multipass transfer tournament:/home/ubuntu/search-agents-strategy-games/results/raw/moves.csv .
multipass transfer tournament:/home/ubuntu/search-agents-strategy-games/results/tables.md .
```

Sanity checks worth running on the finished data:

```powershell
multipass exec tournament -- bash -c "cd search-agents-strategy-games && python3 -c \"
import csv,collections
G=[r for r in csv.DictReader(open('results/raw/games.csv'))]
M=[(r['game_id'],r['ply']) for r in csv.DictReader(open('results/raw/moves.csv'))]
t=collections.Counter(r['tag'] for r in csv.DictReader(open('results/raw/moves.csv')))
print('games',len(G),'expect 2160'); print('dupes',len(M)-len(set(M)),'expect 0')
print('illegal',t.get('illegal_move',0),'agent_error',t.get('agent_error',0),'expect 0 0')\""
```

Expect **2160 games, 0 dupes, 0 illegal_move, 0 agent_error**.

---

## 7. Three findings to carry into the writeup — settled, do not re-derive

1. **Ataxx MCTS is beaten, not starved.** *(Rewritten 2026-08-08 against the
   completed run. The earlier "starved, <5 sims per root move" version was
   measured before the `MCTS_ROLLOUT` fix and is wrong — do not quote it.)*

   Search is **not** the limiting factor: median simulations per root move are
   23.5 (hard) / 90.3 (main) / 347.6 (easy), and **no decision in the whole run
   fell below 1 per root move**. Only Ataxx-hard is thin, and only in its tail
   (p5 = 3.9; 20.1% of decisions below the floor of 10).

   It loses anyway. Head-to-head vs the one-ply heuristic, 40 games per cell:
   **0.050** (hard), **0.175** (main), **0.450** (easy, 95% CI [0.296, 0.604]).
   Versus alpha_beta it scores **0.000** at every budget; versus random,
   **1.000**. Not broken — beaten.

   Two points to carry into the writeup:
   - **Clearing the viability floor is not sufficiency.** Ataxx-main is "ample"
     by the `>= 30` threshold and still scores 0.175.
   - **The budget response is steep and monotone** (0.050 → 0.175 → 0.450 over a
     20x budget increase), reaching parity with the heuristic at 2.0 s.

   Full argument in `PLAN.md`, section "Ataxx MCTS: the starvation reading was
   wrong". **Still report simulations-per-root-move beside every result** — it is
   what distinguishes "lost" from "never searched", and it is what caught this.

2. **Ataxx alpha_beta returns under budget** (mean 1.603 s vs 2.00 s). Correct
   behaviour: early completion on a proven win/loss (`abs(value) >= 1.0`), common
   on Ataxx where games end by elimination. Tagged `normal`.

3. **Runtime is ~8.6 h, not 21 h.** See section 2.

### Also worth recording as a limitation

Wall-clock jitter on this VM reaches roughly +7% on the tail of a per-move budget
(one move in ~1200 during smoke testing), and single moves on Isolation-hard —
budget 0.02 s — absorbed up to +12% when VS Code was running on the guest. Means
are clean (MCTS 100.1–100.2% of budget across all three games). The CSV is **one
sample, not a replayable artifact**; report confidence intervals, not bare
percentages. See `docs/RUNBOOK.md` Q16.

---

## 8. State at handover

- 176 tests passing (20.6 s), via `python3 -m unittest discover -s tests`.
  There is no pytest in this project; `python3 -m pytest` failing is expected.
- `experiments.measure_branching` — clean
- `experiments.calibrate` — PHASE 0 PASSED (21 m 39 s), `results/calibration.txt`
- Smoke tests — `results/smoke2`, `results/smoke3`: 72 games each, 0 illegal_move,
  0 agent_error, 0 orphans, 0 dupes
- Mid-write kill test — **passed on this host**, three variants (see section 4)
- MCTS rollout parameters verified to reach the constructor:
  `tournament.py:43` and `:101-102`, matching `results/calibration.txt:72-94`
- Multipass snapshot `pre-calibration` exists host-side
- Guest systemd timers disabled; `systemd-tmpfiles-clean.timer` masked

> **Before starting any new run:** agents are versioned and frozen once run against.
> `agents/` is v1 and must not change. See `docs/VERSIONING.md`.

**Do not, while the run is going:** install packages, enable timers, run builds
or indexing, start other VMs, or run the test suite. The budgets are wall clock —
any background CPU steals search time and corrupts the measurement.
