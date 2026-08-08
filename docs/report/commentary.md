# Report commentary

Hand-written interpretation, merged into the generated report by section id.
This file is the ONLY place prose belongs - `results/report.md` is generated and
any edit to it is lost on the next run.

Replace each `<!-- TODO -->` with prose. A section left as TODO renders as a
visible `[COMMENTARY NEEDED: id]` callout in the report, so gaps are obvious.

A section id here that matches no slot in the report is an error, not a silent
no-op, so renaming a report section cannot orphan its prose.

<!-- section: overview -->
This is the **v1 tournament**: the full grid of 3 games x 4 agents x 3 time
budgets x 20 trials, played in both seat orders, 2160 games in 7 h 56 m on a
dedicated idle VM.

It exists to answer one question: **how do exact tree search and sampling-based
search compare as state-space size and branching factor grow, when both are held
to the same wall-clock per-move budget?** The three games are chosen to separate
those two axes - Ataxx is the *middle* game by state space but by far the widest,
so any effect that tracks branching rather than state-space size shows up as a
disagreement between the two orderings.

**Zero error moves and zero excluded games.** No agent produced an illegal move
or crashed in 2160 games, so every number below is computed over the complete
grid rather than a filtered subset.

<!-- section: method -->
Read the budget table carefully: **`easy` means *more* time, `hard` means less.**
The names describe difficulty for the agent, not size of budget, and they are easy
to read backwards.

Two design choices matter for interpreting everything downstream. Every pairing is
played in **both seat orders**, so first-move advantage cannot accrue to one agent;
and trials are **interleaved across matchups** rather than run in blocks, so thermal
drift or a noisy neighbour reaches all agents equally instead of accumulating
against whichever ran last.

**The run metadata above is reconstructed, and that is a real weakness.** The MCTS
rollout parameters are not recorded anywhere in the CSVs - they live only as a
constant in `experiments/tournament.py`. This is precisely the parameter whose
silent default caused defect D4 (the tournament ignored calibration entirely) and
whose correction forced the rewrite of finding F3. A reader cannot verify from the
data alone which configuration produced these results; they must trust the tag.
**The first V2 change should be for the tournament to write its own metadata at
startup.**

<!-- section: results -->
**Alpha-Beta wins every cell**, from 0.879 to 1.000. That much is not surprising and
is not the finding.

The finding is in **second place, and it inverts by game**:

| | MCTS vs heuristic |
|---|---|
| Isolation (branching ~6) | **0.892** - MCTS dominates |
| UTTT (branching ~9) | **0.971** - MCTS dominates |
| Ataxx (branching ~25-51) | **0.225** - MCTS is beaten |

MCTS beats a one-ply evaluator comfortably on the two narrow games and loses to it
badly on the wide one. The ordering flips exactly where branching factor jumps, not
where state-space size does - Ataxx is the *middle* game by state space and the
worst for MCTS. **Width, not state-space size, is what defeats sampling-based
search.** This is the study's central result and it is only visible head-to-head;
the field score conflates it with results against the random agent.

The non-transitivity table shows the margins are wildly non-uniform. On Ataxx,
MCTS scores **1.000 against the random agent and 0.225 against the heuristic**.
That pairing is the cleanest evidence available that MCTS is **beaten rather than
broken**: an implementation defect would not produce a perfect record against one
opponent and a poor one against another in the same cell.

Note also that Alpha-Beta's margin over MCTS is itself game-dependent - 0.675 on
UTTT against 1.000 on Ataxx. MCTS is competitive with exact search on the narrow
games and not remotely competitive on the wide one.

<!-- section: budget-response -->
Three different shapes here, and each says something distinct.

**Alpha-Beta is flat.** On UTTT a 20x budget increase moves it 0.883 -> 0.879 ->
0.887 - i.e. not at all. On Isolation it is flat or slightly *negative*. It has
already saturated: extra time buys depth it does not need, because it has solved
or near-solved the position at the smallest budget. This is what makes Isolation a
**control** rather than a degradation datapoint.

**MCTS is the only agent that converts time into strength**, and only on Ataxx:
0.350 -> 0.392 -> **0.483** across a 20x increase, still climbing at the largest
budget. Head to head against the heuristic the same trend is sharper - 0.050 ->
0.175 -> 0.450, reaching statistical parity at 2.0 s. MCTS is not stuck; it is
**under-resourced for the width**, and the budget it would need is well beyond
anything affordable in this grid.

**The heuristic appears to get *worse* with more time** on Ataxx, 0.658 -> 0.625 ->
0.517. It is a one-ply agent and consumes essentially none of the budget (see
instrument validation), so nothing about it changed. Its score falls because its
*opponents* improve. This is a useful warning about field scores: a curve can move
because of agents it is not about.

<!-- section: search-volume -->
This table exists because of defect D9, and the reason is worth stating plainly.
The figure reported here was previously computed as the **mean** of each decision's
simulations-per-legal-move ratio. A position with one legal move contributes a ratio
equal to the entire simulation count, and 10-14% of Ataxx MCTS decisions have exactly
one legal move - so the number was inflated 4-8x by positions where no choice was
made at all. The headline is now the **median**, with the low tail beside it.

**"Ample" is a floor, not a sufficiency criterion.** Ataxx at 0.5 s clears the
`>= 30` threshold comfortably at 90.3 simulations per root move, and still scores
0.175 against a one-ply evaluator. Clearing the floor buys the ability to try each
candidate once; it does not buy competitive play at width 25-30. Any reading of
these results as "MCTS did not get to search" is wrong: **no decision anywhere in
the run fell below one simulation per root move.**

The one genuinely thin cell is **Ataxx-hard**, where 20.1% of decisions fall below
the viability floor and the 5th percentile is 3.9. That is why the p5 and
%-below-floor columns are reported: a single median of 23.5 would have hidden a
fifth of the decisions being starved.

Alpha-Beta's depth tells the same story from the other side: median depth **3-4 on
Ataxx** against 5-7 on Isolation and UTTT. Both paradigms are squeezed by width;
they just fail differently.

<!-- section: instrument-validation -->
**MCTS uses its full budget everywhere** - mean 100.0-100.1% of budget in all nine
cells. It is anytime by construction and stops only when the clock says so, which
is exactly what a wall-clock comparison requires.

**Alpha-Beta's means are the interesting ones.** 90-93% on Ataxx and UTTT, but
**34-53% on Isolation**. It is not being cut off there; it is *finishing* -
completing iterative deepening and returning early on a proven result. An agent that
cannot spend its budget is an agent that has solved the position, which independently
confirms Isolation as the control game.

**The worst overshoot in the entire run is Isolation-hard Alpha-Beta at 138.7%** of
a 0.02 s budget - about 8 ms over. The runbook predicted exactly this cell: at 0.02 s
a single hypervisor scheduling quantum is a large fraction of the budget before the
algorithm does anything. The mean there is 52.9%, so this is a rare tail event, not a
systematic overrun - but Isolation-hard results should carry that caveat.

The heuristic and random agents consume ~0% of budget, as they must.

**A control-game weakness worth flagging.** The heuristic scores **0.750 against the
random agent on Isolation**, against 0.963 on UTTT and 1.000 on Ataxx. A one-ply
evaluator losing 30 games in 120 to random play means the Isolation evaluation
function is weak, or the 5x5 board is small enough that random play stumbles into
adequate moves. Since Isolation is the designated control, this is a caveat on the
control itself, not a minor curiosity.

**First-move advantage is not significant** (first 1095, second 1023, p = 0.1229
over 2118 decisive games). Playing every pairing in both seat orders worked.

**The memory cap binds only at the largest budgets** - all 1380 memory-limited moves
fall in Ataxx-easy (1299) and UTTT-easy (81), and none anywhere else. More time means
a larger transposition table, so the cap is reached only where the search runs long
on a wide game. It never binds on Isolation at any budget.

<!-- section: game-characteristics -->
**The mean game length on Ataxx is misleading and should not be quoted alone.** The
distribution is strongly bimodal: p25 = 10 plies, median = 17, p75 = 76. Games
involving the random agent end in about 10 plies because random play gets eliminated
almost immediately, while agent-versus-agent games run 74-78. A single mean of 39
describes no actual game.

That bimodality is also what broke the original runtime estimate. The projection used
**random self-play** lengths - 182.6 plies on Ataxx - while real agent play is 39 and
the median is 17. The run was estimated at 21 h and took 7 h 56 m. Branching-factor
measurements from random play remain valid, because those are move *counts*; game
*lengths* from random play must not be used to size an agent tournament.

The end-reason split is consistent across budgets and confirms the mechanism: Ataxx
ends by **elimination** more often than by a full board (171 vs 69 at the tightest
budget), Isolation always ends with a player having no legal move, and UTTT ends on a
line in ~95% of games with a small number of early draws.

Isolation and UTTT are by contrast very stable - 13.6-13.7 and 38.6-39.2 plies
regardless of budget - so budget affects *how well* those games are played, not how
long they last.

<!-- section: limitations -->
**This run is one sample, not a replayable artifact.** The budget is wall clock, which
is the only unit fair across two search paradigms, but it means the number of nodes
Alpha-Beta expands depends on how fast the machine happened to be for those
milliseconds. Re-running the identical seeds does not reproduce the identical games.
Every figure here should be read with its interval, never as a bare percentage.

**Resolution.** 120 games per field-score cell and 40 per head-to-head cell give 95%
intervals roughly +/-0.09 and +/-0.15 wide. Differences smaller than that are not
resolvable: Ataxx-easy MCTS at 0.450 against the heuristic **includes 0.5**, so
"reaches parity" is the correct claim and "still loses" is not.

**Single host, single interpreter.** Everything was measured on one 4-vCPU Multipass
guest running Python 3.10.12. A faster interpreter buys more search per budget for all
four agents equally, so the comparison stays fair, but the absolute
simulations-per-root and depth figures are not portable to another machine.

**Timing jitter is real but bounded.** MCTS means sit at 100.0-100.1% of budget, and
the extreme tail reaches 138.7% on the 0.02 s Isolation-hard cell. Conclusions drawn
from that one cell carry more uncertainty than the rest.

**Two known weaknesses in the instrument**, both stated above rather than buried: the
Isolation heuristic scores only 0.750 against random, which is weak for a designated
control; and the MCTS rollout parameters are not recorded in the data, so this run's
configuration is verifiable only via the git tag.

**What this run does not answer.** It does not establish where MCTS would overtake the
heuristic on Ataxx - only that it had not by 2.0 s while still improving. It does not
test enhancements to either paradigm, and it does not vary board size independently of
game, so "width" is confounded with everything else that differs between the three
games.
