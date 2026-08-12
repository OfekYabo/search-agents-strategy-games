# Report commentary - V3 run

Hand-written interpretation, merged into the generated report by
section id. This file is the ONLY place prose belongs -
`results/v3/report.md` is generated and any edit to it is lost.

V1 and V2 have their own commentary files. They are deliberately
separate: the prose describes specific numbers, and merging one run's
onto another's tables would assert figures that no longer hold.

<!-- section: overview -->
This is the **V3 run**: the same grid as V2 - 3 games x 12 directed matchups x
3 budgets x 25 trials - played with the **v3 agents**, 2700 games in 10.03 h.

V3 is the first run that changes how the agents *search* rather than how the
run is *recorded*. Five changes went in together: an Ataxx evaluator
reweighted from 70/30 to 47/53, MCTS subtree reuse between consecutive turns,
independent per-seat RNG streams, bounded-memory instrumentation, and the
removal of duplicated legal-move generation in the hot search paths.

**The result is easy to state and worth stating first: the search changes
worked, and they changed nothing measurable about who wins.** Both halves of
that sentence are supported below, and the combination is more interesting
than either half alone.

**Zero error moves and zero excluded games** over 2700 games, for the third run
running. Run time derived from the data (9.94 h of summed per-move `elapsed_s`)
sits just under the 10.03 h wall clock, so the machine was doing essentially
nothing else.

<!-- section: method -->
Everything in the roster above is **read from `games.csv`**, so this run can
prove its own configuration rather than asking a reader to trust a tag.

**Five changes landed at once, and that limits what this run can attribute.**
If a number had moved, it would not be possible to say which change moved it.
That was an acceptable trade for a first pass - the changes were expected to be
complementary and each was screened separately beforehand - but it means V3
answers "did this bundle help?" and not "which part helped?".

One change deserves specific mention because it alters the sampling rather than
the agents: **V3 gives each seat its own RNG stream**, derived deterministically
from the game seed. V1 and V2 shared one stream between both seats, which meant
the agent that used more random numbers consumed draws the opponent would
otherwise have seen. That was never wrong, but it coupled the two seats. The
consequence for reading this report is that V3 is a genuinely independent
sample from V2 - not the same games played by slightly better agents.

**The host table is part of the result.** The budget is wall clock, so every
simulations-per-root and depth figure here is a statement about this machine:
4 vCPU of an Intel i7-1365U, 3.82 GB RAM, Ubuntu 22.04.5 inside a Multipass
guest. `systemd-detect-virt` reports `microsoft` because Multipass uses Hyper-V
on Windows; that is the hypervisor, not a different operating system.

<!-- section: results -->
**Nothing moved that this run can resolve.** Every pooled head-to-head interval
overlaps its V2 counterpart at 150 games per cell, including the two largest
apparent movements:

| | V2 | V3 | |
|---|---|---|---|
| Ataxx, MCTS vs heuristic | 0.207 [0.150-0.278] | 0.113 [0.072-0.174] | overlapping |
| UTTT, Alpha-Beta vs MCTS | 0.683 [0.605-0.752] | 0.623 [0.544-0.697] | overlapping |

Read those as "not established", not as "no effect". A grid run at this size
resolves differences of roughly 0.13 in a head-to-head cell; both of these are
smaller than that and would need a targeted paired run to settle.

**The headline structure replicates for a third time.** Alpha-Beta wins every
cell. MCTS beats the one-ply heuristic on Isolation (0.860) and UTTT (0.937)
and loses to it on Ataxx (0.113). The ordering still inverts where **branching
factor** jumps rather than where state-space size does - and the observed
branching table now measures that directly from the positions the agents
actually reached: **Ataxx 35.3 mean and 82 at p95**, against 11.3 and 41 for
UTTT and 6.3 and 12 for Isolation.

Three independent samples, on three different days, with different seeds and -
in this run - a different RNG structure entirely, all agreeing. **Width, not
state-space size, is what defeats sampling-based search.**

<!-- section: budget-response -->
The same caution as V2 applies and is worth repeating, because the pattern
looks like a finding and is not one.

**Alpha-Beta appears to weaken with more budget** - UTTT 0.880 -> 0.880 ->
0.850, Isolation 0.967 at the tightest budget down to 0.940. It has not
weakened. Every agent is scored against the same four-agent pool, and MCTS
genuinely improves with budget (UTTT 0.747 -> 0.800, Isolation 0.620 -> 0.707),
so everyone else's *field* score drifts down whether or not they changed. The
heuristic makes this unmistakable: it consumes essentially none of the budget
and still declines on every game as the budget rises.

**MCTS remains the only agent that converts time into strength**, and on Ataxx
it is still climbing at the largest budget: 0.333 -> 0.367 -> 0.413. Note that
this is *lower* at every budget than V2's 0.333 -> 0.387 -> 0.487 while the
shape is identical - consistent with the reweighted evaluator having helped
MCTS's opponents more than MCTS itself, though the per-cell differences are
inside the noise.

<!-- section: search-volume -->
**This is the section that matters in V3, and it carries the run's strongest
result.**

The search changes did exactly what they were meant to do. MCTS simulations per
root move rose sharply against V2:

| | V2 | V3 | |
|---|---|---|---|
| Ataxx-hard | 18.2 | **35.6** | +95% |
| Ataxx-main | 91.7 | **140.5** | +53% |
| Ataxx-easy | 320.8 | **505.8** | +58% |

And the one genuinely thin cell in V2 is no longer thin: **Ataxx-hard fell from
32.4% of decisions below the viability floor to 5.9%**, with p5 rising from 3.9
to 8.9. Every cell in this run reads `ample`.

**MCTS on Ataxx roughly doubled the search it gets, and gained nothing
measurable against a one-ply evaluator.** That is the most direct evidence the
project has produced for finding F3. V1 and V2 could only argue that MCTS was
*not* starved by pointing at simulation counts; V3 tested it by giving MCTS
substantially more search and observing the result. It is **beaten, not
starved**, and now that claim rests on an intervention rather than an
observation.

Subtree reuse works, and how well it works is itself informative:

| game | reuse rate | median nodes reused |
|---|---|---|
| UTTT (all budgets) | 94.6-95.0% | 13-268 |
| Ataxx easy/main | 95.9-96.3% | 3-12 |
| Isolation | 85.8-86.1% | 12-162 |
| **Ataxx-hard** | **64.7%** | **1** |

Ataxx-hard is the outlier for a structural reason: at a 0.1 s budget the tree is
small (median 568 nodes) against a mean branching factor above 30, so the
opponent's actual reply is frequently a node that was never expanded. **Reuse
helps least exactly where MCTS is weakest** - the same width problem, appearing
in a second place.

Alpha-Beta's depth is unchanged from V2 at median 3-4 on Ataxx against 5-7
elsewhere. Both paradigms are squeezed by width; they fail differently.

<!-- section: instrument-validation -->
**MCTS uses its full budget everywhere** - 100.0-100.6% of budget in every cell.

**Alpha-Beta spends 34.5-53.6% of its budget on Isolation** against 92-93% on
Ataxx and UTTT. It is finishing, not being cut off - an agent that cannot spend
its budget has solved the position - which independently confirms Isolation as
the control game.

**The timing tail got worse, and this is the one instrument result that should
temper confidence.** The worst overshoot in V3 is Isolation-main Alpha-Beta at
**204.8%** of a 0.1 s budget, with Isolation-hard MCTS at 173.5% and
Isolation-hard Alpha-Beta at 154.3%. V2's worst was 147.3%. These remain rare
tail events against means of 45.0% and 100.6%, and Isolation is 2.5% of the
run, but **Isolation's tight budgets are the least trustworthy timing in the
study** and results there should be quoted with that caveat.

**The weak control persists and is now better characterised.** The heuristic
scores **0.833 against the random agent on Isolation** (125-0-25), against 0.973
on UTTT and 1.000 on Ataxx. V2 measured 0.780; the intervals overlap, so this is
the same finding rather than an improvement. Three runs have now failed to
explain why a one-ply mobility evaluator loses a sixth of its games to random
play on a 5x5 board. The declined-win defect fixed in V2 was not the cause, and
V3 did not change the Isolation evaluator at all.

**MCTS lost a game to the random agent on Isolation** (149-0-1), having gone
150-0-0 in V2. One game in 150 is noise, but it belongs on the record.

**First-move advantage is not significant** (first 1368, second 1280, p = 0.0909
over 2648 decisive games). Across V1, V2 and V3 the p-value has drifted 0.1229,
0.0878, 0.0909 without crossing 0.05. Playing every pairing in both seat orders
means any residual advantage is shared equally regardless.

<!-- section: game-characteristics -->
**Ataxx games are longer than V2's and end differently.** Mean plies rose from
34.8/40.9/41.5 to 38.5/43.6/44.2, and eliminations gave way to full boards -
at the easy budget V2 ended 134 board-full against 166 eliminations, while V3
ends 147 against 153. The reweighted evaluator, which now weights exposure
slightly above material, produces less decisive early play and more games that
run to the end of the board.

That is a real behavioural change from a one-line reweighting, and it is worth
noticing that it showed up in game *length* long before it showed up in any
win rate - where, as the results section says, it still has not.

**The mean still should not be quoted alone on Ataxx.** Mean 44.2 against a
median of 31.5 at the easy budget: games involving the random agent end quickly
by elimination while agent-versus-agent games run far longer, and no single
game resembles the mean.

Isolation and UTTT remain stable at 13.1-13.4 and 37.9-39.1 plies regardless of
budget, so budget affects **how well** those games are played, not how long they
last.

**Where the time went** matters for planning any future run: Ataxx-easy and
UTTT-easy alone are **75.6%** of the 9.94 hours. All of Isolation is under 3%.

<!-- section: limitations -->
**Five changes landed together, so this run cannot attribute an effect to any
one of them.** Nothing here says which of the evaluator reweighting, subtree
reuse, RNG separation or the hot-path cleanup was responsible for any number.
That was a deliberate trade for a first pass and it is the main methodological
cost of this run.

**No V2-to-V3 difference is resolvable.** Every interval overlaps. With 150
games per pooled head-to-head cell the run resolves differences of roughly 0.13,
and everything observed is smaller. Read the comparison as "the bundle did not
produce a large effect", not as "the bundle did nothing".

**The comparison that would settle it has not been run.** Playing v2 agents
directly against v3 agents in one tournament is a *paired* design and would
resolve a much smaller difference than comparing each version against a common
four-agent field. The harness cannot do it yet - `--agent-version` selects one
version for a whole run - and that is the single most valuable piece of
remaining work.

**Isolation's timing tail is the worst in the study**, reaching 204.8% of a
0.1 s budget on one Alpha-Beta decision. Conclusions from Isolation's tight
budgets carry more uncertainty than anything else here.

**This run is one sample**, as V1 and V2 were. What three runs buy is not
certainty but agreement: the headline has now survived three independent
samples, different seeds, and a change in RNG structure.

**Single host, single interpreter**, both recorded in the method section. A
faster machine would buy more search per budget for all four agents equally, so
the comparison would survive, but the absolute simulations-per-root and depth
figures would not.

**What this run does not answer.** It does not establish where MCTS would
overtake the heuristic on Ataxx - only that doubling its search did not get it
there. It does not isolate any single V3 change. And it still does not explain
the weak Isolation control.
