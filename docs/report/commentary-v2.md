# Report commentary — V2 run

Hand-written interpretation, merged into the generated report by section id.
This file is the ONLY place prose belongs - `results/v2/report.md` is generated
and any edit to it is lost on the next run.

V1 has its own commentary in `commentary.md`. They are deliberately separate:
the prose describes specific numbers, and merging v1's onto v2's tables would
assert figures that no longer hold.

<!-- section: overview -->
This is the **V2 run**: the same grid as V1 at 25 trials instead of 20, played
with the **v2 agents** (`agents/v2/`, `evaluation/v2/`), 2700 games in 9 h 49 m.

**V2 exists to do two things, and neither is "find new results".**

1. **Replicate.** V1 was a single sample under a wall-clock budget, which the
   project's own methodology says is not a replayable artifact. V2 is an
   independent sample, on a different day, with different seeds beyond trial 19
   and 25% more games per cell. Whether the headline survives that is worth more
   than any individual number in it.
2. **Instrument.** V1 could not say from its own data which rollout parameters
   produced it. V2 records the agent version and every agent's hyperparameters
   **per game**, plus a full `run_meta.json` written at startup. This run is
   self-describing; V1's method section had to be reconstructed.

**Zero error moves and zero excluded games**, again, over 2700 games. And the
run time derived from the data (9.81 h of summed per-move `elapsed_s`) matches
the wall clock (9.81 h) exactly, which means the machine was never doing
anything else - no stall, no contention, no restart.

<!-- section: method -->
The roster above is **read from `games.csv`, not from a configuration file**.
That is the substantive change from V1, whose equivalent section was
reconstructed from memory and said so.

The distinction matters more than it sounds. Defect D4 was the tournament
silently running MCTS rollout defaults that calibration had ranked *worst*, and
nothing in the resulting data could have revealed it. The parameters now travel
with every game row, so a future reader can verify from the evidence which
configuration produced which result rather than trusting a tag.

Two design choices carried over from V1 and still load-bearing: every pairing is
played in **both seat orders**, and trials are **interleaved across matchups**
rather than run in blocks, so drift or background load reaches all agents
equally instead of accumulating against whichever ran last.

**`easy` still means *more* time and `hard` less.** The names describe difficulty
for the agent, not the size of the budget.

**The host table is part of the result, not bookkeeping.** The budget is wall
clock, so every simulations-per-root and depth figure in this report is a
statement about *this machine*: 4 vCPU of a 13th-gen Intel i7-1365U, 3.82 GB RAM,
Ubuntu 22.04.5, inside a Multipass guest. `systemd-detect-virt` reports
`microsoft` because Multipass uses Hyper-V on Windows - that is the hypervisor,
not a different operating system. A faster host would buy more search per budget
for all four agents equally, so the *comparison* would survive; the absolute
figures would not.

<!-- section: results -->
**The V1 result replicates.** Every pooled head-to-head moved by at most **0.030**
between runs, against a cell resolution of roughly 0.11. That is the single most
important line in this report: a wall-clock-budgeted tournament is one sample,
and this is the second one agreeing with the first.

**Alpha-Beta wins every cell**, 0.860 to 1.000. As in V1, the interesting
structure is in second place, and it still inverts by game:

| MCTS vs the one-ply heuristic | V1 | V2 |
|---|---|---|
| Isolation (branching ~6) | 0.892 | **0.873** |
| UTTT (branching ~9) | 0.971 | **0.950** |
| Ataxx (branching ~25-31) | 0.225 | **0.207** |

MCTS beats a one-ply evaluator comfortably on the two narrow games and loses to
it badly on the wide one. The ordering flips where **branching factor** jumps,
not where state-space size does - Ataxx is the *middle* game by state space and
the worst for MCTS. **Width, not state-space size, is what defeats sampling-based
search**, and it is now a twice-measured result rather than a single observation.

The non-transitivity table carries the cleanest single piece of evidence in the
study: on Ataxx, MCTS scores **1.000 against the random agent and 0.207 against
the heuristic**. An implementation defect does not produce a perfect record
against one opponent and a poor one against another in the same cell. MCTS is
**beaten, not broken**.

<!-- section: budget-response -->
Read this section carefully, because the most eye-catching pattern in it is an
artifact and mistaking it for a finding would be easy.

**Alpha-Beta appears to get *worse* with more time.** On UTTT it goes 0.910 →
0.873 → 0.860 across a 20x budget increase; on Isolation, 0.993 at the *tightest*
0.02 s budget down to 0.920 at 0.5 s. Taken at face value that would say extra
search hurts an exact searcher, which is absurd.

**It is a property of the field score, not of Alpha-Beta.** Every agent is scored
against the same four-agent pool, and MCTS *does* improve with budget - 0.697 →
0.773 → 0.797 on UTTT, 0.580 → 0.747 → 0.740 on Isolation. When one member of the
pool gets stronger, everyone else's field score falls, whether or not they
changed. The heuristic shows the same thing even more starkly: it consumes
essentially none of the budget (see instrument validation) and yet declines on
every game as the budget rises.

The honest reading is the one V1 reached: **Alpha-Beta has saturated.** It has
solved or near-solved these positions at the smallest budget, so extra time buys
it nothing, and its *relative* score drifts down as its opponents improve. This
is exactly why Isolation is a **control** rather than a degradation datapoint.

**MCTS is the only agent that converts time into strength**, and the effect is
largest where it is weakest: on Ataxx, 0.333 → 0.387 → **0.487** across a 20x
budget increase, still climbing at the largest budget. Head-to-head against the
heuristic the same trend is sharper. MCTS is not stuck on Ataxx; it is
**under-resourced for the width**, and the budget it would need is well beyond
anything this grid can afford.

<!-- section: search-volume -->
No decision anywhere in this run fell below one simulation per root move, so
"MCTS never got to search" is false everywhere. But **clearing the viability
floor is not sufficiency**: Ataxx-main sits at 91.7 simulations per root move,
comfortably "ample" by the `>= 30` threshold, and still scores 0.207 against a
one-ply evaluator. The floor buys the ability to try each candidate once. It does
not buy competitive play at width 25-31.

**Ataxx-hard got thinner than in V1** - 32.4% of decisions below the floor
against 20.1%, with the median falling 23.5 → 18.2. This is worth stating
precisely, because the obvious explanation is wrong:

- **The machine did not slow down.** Budget compliance is identical at 100.1%
  mean, and V2's tail is actually *better* (106.9% max against V1's 114.2%).
- **Simulations barely moved** - median 360 → 346 per decision.
- **The denominator grew.** MCTS faced a mean of **30.72 legal moves against
  25.34** in V1. More games ended by elimination (220 of 300 against 171 of 240)
  and games ran slightly longer, leaving MCTS deciding in more mid-game Ataxx
  positions - which is exactly where branching peaks.

So the ratio fell because the positions were wider, not because the search was
slower. That is a small illustration of a general hazard with ratios, and the
reason `p5` and `% below floor` are reported beside the median rather than a
single number.

Alpha-Beta tells the same story from the other side: median depth **3-4 on
Ataxx** against 5-7 on Isolation and UTTT. Both paradigms are squeezed by width;
they fail differently.

<!-- section: instrument-validation -->
**MCTS uses its full budget everywhere** - mean 100.0-100.2% of budget in all
nine cells. It is anytime by construction and stops only when the clock says so,
which is what a wall-clock comparison requires.

**Alpha-Beta's means are the diagnostic ones.** 92-93% on Ataxx and UTTT, but
**34.7-53.1% on Isolation**. It is not being cut off there; it is *finishing* -
completing iterative deepening and returning on a proven result. An agent that
cannot spend its budget has solved the position, which independently confirms
Isolation as the control game.

**The worst overshoot in the run is again Isolation-hard**: Alpha-Beta at 147.3%
and MCTS at 142.1% of a 0.02 s budget - roughly 8-9 ms over. Both are rare tail
events against means of 53.1% and 100.2%, and the cell was predicted to be the
most exposed: at 0.02 s a single hypervisor scheduling quantum is a large
fraction of the budget before the algorithm does anything. **Isolation-hard
results carry more timing uncertainty than any other cell** and should be quoted
with that caveat.

**The weak control persists, and the obvious explanation has been ruled out.**
The heuristic scores **0.780 against the random agent on Isolation**, against
0.957 on UTTT and 1.000 on Ataxx. V2 fixed a real defect here - v1's one-ply
agent declined an available immediate win in 28.0% of such positions on Isolation
- and the score moved only from 0.750 to 0.780, well inside the interval.
Declining a win usually still wins from a mobility advantage, so the rate of
declined wins was never the rate of lost games. **Why a one-ply mobility
evaluator loses a fifth of its games to random play on a 5x5 board is still
unexplained**, and it is the first open lead for v3.

**First-move advantage is not significant** (first 1373, second 1284, p = 0.0878
over 2657 decisive games). Closer to the line than V1's 0.1229 and worth watching
across runs, but playing every pairing in both seat orders means any residual
advantage is shared equally and cannot favour one agent.

**The memory cap binds only at the largest budgets** - 1637 memory-limited moves,
all Alpha-Beta, concentrated where a long search fills the transposition table.
It never binds on Isolation at any budget.

<!-- section: game-characteristics -->
**Ataxx game length is bimodal and its mean should not be quoted alone.** At the
easy budget the mean is 41.5 plies against a median of 20.5; at hard, 34.8 against
16.0. Games involving the random agent end in roughly ten plies because random
play is eliminated almost immediately, while agent-versus-agent games run three
to four times longer. A single mean describes no actual game.

That gap is also what broke the original runtime estimate. The V1 projection used
**random self-play** lengths - 182.6 plies on Ataxx - while real agent play is
under 42. The run was projected at 21 h and took under 8. Branching-factor
measurements from random play remain valid, because those are move *counts*; game
*lengths* from random play must not be used to size an agent tournament.

The end-reason split confirms the mechanism and shows a budget effect: Ataxx ends
by **elimination** far more often at the tight budget (220 of 300) than at the
generous one (166 of 300), because weaker play gets wiped out rather than filling
the board. Isolation always ends with a player having no legal move; UTTT ends on
a line in about 95% of games with a handful of early draws.

Isolation and UTTT are by contrast very stable - 13.3-13.7 and 38.4-39.6 plies
regardless of budget - so budget affects **how well** those games are played, not
how long they last.

**Where the time went** is worth noting for anyone planning a future run: two
cells, Ataxx-easy and UTTT-easy, account for **75.7%** of the entire 9.81 hours.
All of Isolation is 2.5%. Any attempt to shorten a run, or to buy more trials,
has to start there.

<!-- section: limitations -->
**This run is one sample, and so was V1.** The budget is wall clock - the only
unit that is fair across two search paradigms - which means the number of nodes
Alpha-Beta expands depends on how fast the machine happened to be for those
milliseconds. Re-running identical seeds does not reproduce identical games. What
V2 adds is not certainty but **agreement**: two independent samples reaching the
same conclusions is materially stronger than one, and every claim in this report
should still be read with its interval rather than as a bare percentage.

**Resolution.** 150 games per field-score cell and 50 per head-to-head cell give
95% intervals roughly ±0.08 and ±0.13 wide. Differences smaller than that are not
resolvable, and the largest V1-to-V2 movement was 0.030 - comfortably inside the
noise, which is the correct way to read "it replicated". It also sets the bar for
v3: **a change that moves a head-to-head score by less than about 0.13 will not
be visible in a grid run** and needs a targeted head-to-head at far higher
repetition instead.

**Field scores are not absolute strength.** As section 4 shows, an agent's field
score falls when *other* agents in the pool improve, even if it has not changed.
Head-to-head numbers are the ones that support claims about a specific matchup.

**Single host, single interpreter.** One Multipass guest - 4 vCPU of an Intel
i7-1365U, 3.82 GB RAM, Ubuntu 22.04.5, Python 3.10.12 - all now recorded in the
method section rather than remembered. A faster host or interpreter buys more
search per budget for all four agents equally, so the comparison stays fair, but
**the absolute simulations-per-root and depth figures are not portable** and
should always be quoted with the machine.

Note also that 4 vCPU does not mean the run used four cores: the harness is
strictly single-threaded and sequential. The spare cores exist to keep anything
else on the guest from stealing time mid-decision, which is isolation rather than
speed.

**Two known weaknesses in the instrument.** Isolation-hard carries the largest
timing tail in the run (147.3% of a 0.02 s budget). And the Isolation heuristic
scores only 0.780 against random, which is weak for a designated control and now
demonstrably *not* explained by the defect V2 fixed.

**What this run does not answer.** It does not establish where MCTS would overtake
the heuristic on Ataxx - only that it had not by 2.0 s while still improving. It
does not test enhancements to either paradigm. And it does not vary board size
independently of game, so "width" remains confounded with everything else that
differs between the three games.
