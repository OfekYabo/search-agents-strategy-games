# Gamebook: Ataxx 7x7 (no blocked squares)

> Role in this project: **medium domain** (log10 state space ~ 23.7).
> Status: ruleset **confirmed**. Remaining non-blocking gaps tracked in section 9.

---

## 1. Provenance and naming

The game was invented in 1988 by **Dave Crummack and Craig Galley** for Wise Owl
Software, under the name **Infection**. Wise Owl sold the rights to Virgin
Mastertronic, which licensed the game to Leland Corporation; Leland released it as
the arcade title **Ataxx** in 1990. Virgin separately published its own version as
**Spot** (NES, PC, Game Boy), and the same game appears as the "Microscope Puzzle"
in the 1993 CD-ROM game *The 7th Guest*.

**We use the name "Ataxx".** It is the name used throughout the game-AI and
game-search literature, it is the title of the game's Wikipedia article, and it is
what current online implementations use - so it is both the most common and the most
current choice.

Other names in circulation are recorded here only so that sources found under them
are recognisable as the same game: *Infection* (the 1988 original), *Spot*,
*SlimeWars*, *Frog Cloning*. **Assimilation** is a shareware *variant* with modified
mechanics rather than another name for the same game, and its rules should not be
used as a source.

> **Spelling.** PLAN.md and the README originally wrote "Attax" throughout. That is
> not one of the game's names - it was a typo. It mattered because this project
> imports an external complexity figure for the game (average branching factor ~60,
> average game length ~100 plies); a report citing a figure for a game whose name it
> consistently misspells invites doubt about the citation. **Fixed: all ten
> occurrences across PLAN.md and README.md now read "Ataxx".**

Our ruleset is faithful to standard Ataxx with one declared deviation: we use **no
blocked squares** (section 6.1).

---

## 2. Board and notation

A 7x7 grid, cells `(r, c)` with `r, c` in `0..6`, origin at the top-left. Each cell
is empty, held by Player 1, or held by Player 2. There are no permanently blocked
cells in our variant.

Distances below are **Chebyshev distance**: `dist((r1,c1),(r2,c2)) = max(|r1-r2|,
|c1-c2|)`. Chebyshev distance 1 is the eight surrounding cells; Chebyshev distance 2
is the ring of 16 cells outside those.

**Move notation (for CSV logging and replay).** Cells are named `<file><rank>` with
files `a`-`g` left to right and ranks `1`-`7` bottom to top, so `(r, c)` maps to
file `chr(ord('a') + c)` and rank `7 - r`. A move is written:

| Form | Meaning | Example |
|---|---|---|
| `<dest>` | clone to `dest` | `b6` |
| `<src><dest>` | jump from `src` to `dest` | `a7c5` |
| `--` | pass (forced; see 4.4) | `--` |

This matches the convention used by existing Ataxx engines, so logged games can be
pasted into an external implementation to check them. Every move must be
round-trippable: parsing a logged string back must yield the same move object.

---

## 3. Starting position

```
      c0  c1  c2  c3  c4  c5  c6
 r0    1   .   .   .   .   .   2
 r1    .   .   .   .   .   .   .
 r2    .   .   .   .   .   .   .
 r3    .   .   .   .   .   .   .
 r4    .   .   .   .   .   .   .
 r5    .   .   .   .   .   .   .
 r6    2   .   .   .   .   .   1
```

- Player 1 holds `(0,0)` and `(6,6)`; Player 2 holds `(0,6)` and `(6,0)`.
- The remaining 45 cells are empty. **Player 1 moves first.**

The placement is diagonally opposed, so the position is symmetric under a 180-degree
rotation and neither player starts with a positional edge.

---

## 4. Rules of play

**4.1 The two move types.** On your turn you must make one move, of either type:

- **Clone.** Choose an empty cell at Chebyshev distance 1 from any piece you own. A
  new piece of your colour appears there. **The source piece stays on the board**, so
  your piece count rises by one.
- **Jump.** Choose one of your pieces and an empty cell at Chebyshev distance
  *exactly* 2 from it. That piece moves there; its original cell becomes empty. Your
  piece count is unchanged.

The two move sets, drawn around a piece at `P`:

```
    J  J  J  J  J        C = clone destination  (Chebyshev distance 1,  8 cells)
    J  C  C  C  J        J = jump destination   (Chebyshev distance 2, 16 cells)
    J  C  P  C  J
    J  C  C  C  J        All 24 cells are candidates; only the empty ones
    J  J  J  J  J        are legal.
```

**The 16 jump cells are the whole outer ring** - the 8 straight and diagonal
two-steps *and* the 8 knight-shaped cells. Rule statements that describe the jump as
"a knight move" or as "two spaces in a straight line" each name only half the ring;
both halves are legal. Implementing only one half is an easy and silent bug (see 7).

**4.2 Move identity, and why it matters.** A clone is fully determined by its
**destination** - cloning into cell `X` produces the same resulting position no
matter which adjacent friendly piece is regarded as the source. Clone moves are
therefore **deduplicated by destination**. A jump is identified by the
`(source, destination)` pair, because the source cell it vacates differs.

Getting this wrong inflates the branching factor substantially and would make our
measured figure incomparable with the ~60 reference.

**4.3 Conversion.** Immediately after the piece lands, **every opponent piece in the
eight cells adjacent to the destination changes to the mover's colour** - up to 8
pieces at once. Conversion is not chained: only the destination's own neighbours are
affected, not the neighbours of converted pieces. Conversion never changes the total
number of occupied cells.

**4.4 Passing.** Passing is **forced, never optional**. A player who has at least one
legal move *must* make one; a player with no legal move *must* pass, and does **not**
lose by doing so. There is no voluntary pass in Ataxx, so a move generator must never
emit a pass alongside real moves - the pass is the move list when, and only when, the
move list would otherwise be empty.

> PLAN.md line 71 originally stated that a player with no legal move loses. **That is
> incorrect** and is corrected here; the sources in section 8 are explicit that
> passing is forced but not losing. This is a substantive rule fix, not a wording
> change: under the erroneous rule a temporarily-boxed-in player loses a game they
> would often go on to win.

**4.4.1 Can both players be stuck at once? No - and this is provable.**

The worry is a deadlock: neither player can move, the board is not full, and the game
never ends. It cannot happen.

*Two facts.* First, the **total number of occupied cells never decreases**: a clone
adds one, a jump vacates one cell and fills another for a net zero, and conversion
only recolours. Starting from 4 pieces, the board therefore always holds **at least 4
pieces**. Second, a player has a legal move exactly when some empty cell lies within
Chebyshev distance 2 of one of their pieces.

*The argument.* Suppose neither player has a legal move and at least one cell is
empty. Then no occupied cell is within distance 2 of any empty cell - equivalently,
**every cell within distance 2 of an empty cell is itself empty**. Pick any empty
cell; all cells within distance 2 of it are empty; each of those is empty, so all
cells within distance 2 of *them* are empty as well. The 7x7 board is connected under
distance-2 steps, so this propagates to the entire board, forcing every cell to be
empty. That contradicts the board always holding at least 4 pieces.

*Conclusion.* **Whenever an empty cell exists, at least one player has a legal move.**
At most one player can be stuck at a time, and if no empty cell exists the board is
full and terminal condition 4.5.1 has already fired. A double pass is therefore
**unreachable**, and no deadlock exists.

This does *not* rescue us from the termination problem in 4.6 - jump-only shuffling
keeps the empty count fixed and can still run forever. The two are separate issues.

**4.5 Terminal conditions.** The game ends as soon as any of these holds:

1. the board is full;
2. a player has zero pieces (that player loses regardless of count);
3. both players pass in succession - **unreachable in practice**, see 4.4.1; keep it
   implemented as a defensive assertion rather than as a real exit path;
4. the no-progress rule in 4.6 fires - 30 plies without progress, or the 300-ply cap.

**4.6 The no-progress rule.** *[CONFIRMED]*

Rules 1-3 alone **do not guarantee the game ends.** A clone raises the occupied-cell
count by one; a jump leaves it unchanged; conversion leaves it unchanged. So a
sequence consisting only of jumps can continue indefinitely, shuffling pieces back
and forth without ever filling the board. Real Ataxx implementations all impose some
no-progress cutoff; ours must too, or a tournament run can hang forever.

The rule, mirroring the chess 50-move rule:

> A ply counts as **progress** if it is a clone, or if it converted at least one
> opponent piece. If **30 consecutive plies** occur with no progress, the game ends
> and is scored by piece count exactly as in 4.7.
>
> A **hard cap of 300 plies** sits behind it: on reaching it the game ends and is
> scored the same way. Nothing can hang.

A **pass is not progress** and increments the counter like any other ply - otherwise
a player stuck passing while the opponent shuffles jumps would stall the counter
forever, which is precisely the case the rule exists to catch.

Both figures are chosen against the measured average game length of ~100 plies (5.2):
30 plies of pure repositioning is well beyond any plausible genuine manoeuvre, and
the 300-ply cap is roughly triple a typical game, so it should effectively never fire
on live play. **Log every game that ends by either rule**, with which one fired - if
the no-progress rule turns out to fire often, 30 was too tight and the figure needs
revisiting rather than silently distorting the results.

**4.7 Scoring.** At termination, the player with more pieces wins. Equal counts are a
**draw**. A player reduced to zero pieces loses.

---

## 5. Derived properties

**5.1 State-space upper bound.**

```
2  x  3^49  =  2 x 2.39 x 10^23  ~  4.78 x 10^23        log10 = 23.7
|     |
|     +--- each of 49 cells is empty, P1, or P2
+--------- side to move
```

Loose, as usual: it counts positions unreachable from the fixed start, and positions
where one colour has no pieces yet play continues.

A **tighter published figure** for the same 7x7 board is `5.982483 x 10^22`
(log10 22.8), which excludes end-game positions where every remaining piece is one
colour. It is about a quarter of our `3^49` term, so the two are consistent - ours is
simply the looser bound. Keep `2 x 3^49` as the headline for form-consistency with
the other two games, and cite the tighter figure alongside it. The same source gives
a game-tree complexity of `1.371545 x 10^896`. See 9.2 for how much weight that
source can carry.

**5.2 Branching factor.**

| Quantity | Value | Source |
|---|---|---|
| Upper bound | **<= 17e** (`<= 765`) | derived below; `e` = empty cells, at most 45 |
| Ply 1, measured | **~20** | Ribeiro and Figueiredo 2018 |
| Peak, measured | **92** around ply 25; **~90** again around ply 52 | Ribeiro and Figueiredo 2018 |
| Typical average | **~60** | old Wikipedia revision - **not peer-reviewed**, see 9.2 |
| Our average | *pending* | to be measured by the random agent against the tested implementation |

The measured figures from Ribeiro and Figueiredo are the better reference: they are
peer-reviewed, and their shape is informative in its own right. Branching factor is
**not monotonic** - it starts near 20, roughly quadruples to a mid-game peak of 92,
falls, and peaks again near ply 52. Our own measurement should reproduce that
double-humped curve; if it comes out flat, the move generator is wrong. This makes
them a far better validation target than a single average.

The bound follows cleanly from move identity (4.2): **every legal move lands on an
empty cell**, and a given empty cell can be the destination of *at most one*
deduplicated clone and *at most 16* jumps, one per cell in its distance-2 ring. So
`b <= 17e`, giving `17 x 45 = 765` at most.

That figure is unreachable in practice - it needs every empty cell simultaneously
ringed by friendly pieces at both distances, while 45 cells stay empty. The ~60
reference is the number to reason with, and it is the largest average branching
factor of the three games in this project.

**5.3 Game length.** The reference average is ~100 plies. **There is no provable
maximum** from the published rules alone, for the reason given in 4.6; with our rule
the hard bound is the **300-ply cap**.

**5.4 A full board can never be a draw.** The 49 cells are odd in number, so when the
board fills, `n1 + n2 = 49` and the two counts cannot be equal. **Draws are therefore
only reachable with empty cells still on the board** - that is, via the double-pass
condition (4.5.3) or the no-progress cutoff (4.6), and only when the counts happen to
be level. This matters for the experiment: since PLAN.md reports draw rate as a
headline metric, the Ataxx draw rate is effectively a measure of how often games end
in stalemate rather than completion, which is a different quantity from the UTTT draw
rate. The report should not compare the two directly without saying so.

**5.5 Note for the report.** Branching factor across the three games is
**not monotonic** in state-space size: Ataxx (~60) is by far the widest, while
Ultimate Tic-Tac-Toe (usually <= 9) has a state space fifteen orders of magnitude
larger. UTTT gets its size from *depth* - up to 81 plies - not width. Any claim in
the report about "harder games" must therefore say which axis it means, because the
two orderings genuinely disagree.

---

## 6. Alternatives considered and rejected

**6.1 Blocked squares.** The arcade original and several implementations support
symmetrically-placed blocked cells. *Rejected:* they are an optional variant, they add
a board-configuration parameter we have no reason to vary, and omitting them keeps the
`3^49` state-space derivation exact in form.

> **Correction to PLAN.md.** PLAN.md line 58 attributes the ~60 / ~100 figures to
> "canonical Ataxx (7x7 with two fixed blocked squares)". **That attribution is not
> supported by any source we could find.** The source of those numbers describes a
> *standard* 7x7 board and does not mention blocked squares at all, and the
> peer-reviewed measurements in 5.2 are likewise on an unobstructed board. The
> parenthetical should be removed rather than corrected, since there is no
> blocked-square reference to point at.

Because our board and the reference boards are both unobstructed 49-cell boards, our
measurements should be *directly* comparable rather than needing an adjustment - which
is a better position than the one PLAN.md assumed.

**6.2 Treating "no legal move" as a loss** (what PLAN.md currently says). *Rejected:*
it contradicts the published rules, and it is not a harmless simplification - it
changes which side wins in a common class of positions where a player is temporarily
boxed in but would recover.

**6.3 The "opponent fills the remaining squares" shortcut.** Several rule statements
say that once one player can no longer move, the opponent simply fills every
remaining empty cell and the game is scored. *Rejected in favour of the pass loop in
4.4:* the two are not quite equivalent. The pass loop lets the mobile player fill
only the cells they can actually reach, whereas the shortcut hands them cells that
may be unreachable. Running the loop is both stricter and simpler to implement
correctly, and it costs nothing because the moves are forced anyway.

**6.4 Counting clone moves by `(source, destination)` pair.** *Rejected:* the
resulting positions are identical, so this is pure move-list duplication. It would
inflate the measured branching factor, waste search effort on transpositions, and
make our figure incomparable with the external reference.

**6.5 Chained conversion** (converted pieces in turn convert their own neighbours).
*Rejected:* not part of any published Ataxx ruleset; it is a different game.

---

## 7. Implementation notes

- Generate both move sets by scanning the offsets `dr, dc` in `-2..2` excluding
  `(0,0)`, and classifying by `max(abs(dr), abs(dc))`: `1` is a clone, `2` is a jump.
  This yields all 8 clone and all 16 jump cells with no special-casing, and avoids
  the common bug of enumerating jumps as eight hand-written straight-line offsets,
  which silently drops the eight knight-shaped destinations.
- Move generation should collect clone destinations in a `set` and jump moves in a
  `list`, then concatenate - this gives the deduplication in 4.2 for free.
- Conversion touches at most 8 cells and never changes the occupied count, which
  makes an incremental piece-count update trivial and cheap.
- The terminal test must distinguish "no legal move" (pass) from "no pieces" (loss).
  Conflating them reintroduces the bug in 6.2.
- A natural state encoding is two 49-bit bitboards plus the side to move; conversion
  is then a masked bitwise operation over the 8-neighbourhood of the destination.
- **The full state is larger than the board.** It is `(p1_bitboard, p2_bitboard,
  side_to_move, plies_since_progress)`. The counter is easy to forget and it is
  load-bearing: it drives the termination rule in 4.6.
- **The progress counter must go into the transposition-table key.** Two positions
  with identical bitboards but different progress counts have genuinely different
  values - one may be a move away from a no-progress cutoff and the other not - so
  keying on the board alone lets Alpha-Beta return a cached value that is simply
  wrong.
- A `previous_ply_was_a_pass` flag is **not** needed for correctness, since 4.4.1
  shows a double pass cannot occur. Track it anyway as a cheap assertion: if it ever
  fires, move generation or the terminal test has a bug.
- *Optional optimisation, low priority:* the start position is symmetric under both
  180-degree rotation and reflection in the main diagonal, so reachable positions
  come in equivalence classes of up to four. Canonicalising the TT key over that
  group would cut transposition-table pressure, which matters under the memory cap.
  Only worth doing if the cap turns out to bind in the pilot.

---

## 8. References

**Playable reference**

- [Ataxx - onlinesologames.com](https://www.onlinesologames.com/ataxx) - a playable implementation matching our variant: 7x7, corner start, no blocked squares, forced passing, ends when the board fills or a player is eliminated. Useful for getting a feel for the game and for eyeballing our move generator against. Note its jump description ("an L-shaped jump, identical to a knight move in Chess") names only half the legal ring - see 4.1.

**Video explanation**

- [Ataxx explained (YouTube)](https://www.youtube.com/watch?v=lXNcRy9DZxs) - walkthrough of clone and jump moves and the conversion rule.

**Academic sources**

- **Ribeiro, L. and Figueiredo, D. R.** *Performance of Monte Carlo Tree Search Algorithms when Playing the Game Ataxx.* XV Encontro Nacional de Inteligencia Artificial e Computacional (ENIAC 2018), Sao Paulo, Brazil, October 2018. DOI [10.5753/eniac.2018.4423](https://doi.org/10.5753/eniac.2018.4423).
  - [Publisher page (SBC OpenLib, open access)](https://sol.sbc.org.br/index.php/eniac/article/view/4423) | [Author's PDF](https://leoribeiro.github.io/papers/mcts-ataxx-eniac2018.pdf) | [Semantic Scholar](https://www.semanticscholar.org/paper/Performance-of-Monte-Carlo-Tree-Search-Algorithms-Ribeiro-Figueiredo/fedbf0da6588ebd075d13ca7dbcaa2976e89338e)
  - **Archived locally:** [`docs/references/ribeiro-figueiredo-2018-mcts-ataxx.pdf`](../references/ribeiro-figueiredo-2018-mcts-ataxx.pdf)
  - Our primary source for measured branching factors (5.2), and directly relevant related work - it evaluates MCTS variants on this exact game.
- [leoribeiro/mcts-ataxx (GitHub)](https://github.com/leoribeiro/mcts-ataxx) - the authors' MCTS implementation for Ataxx. Useful as an independent implementation to cross-check our move generator and measured branching factors against.

**Complexity figures of uncertain provenance**

- [Ataxx - en-academic (mirror of a former Wikipedia revision)](https://en-academic.com/dic.nsf/enwiki/219355) - source of the widely-repeated "average ~100 plies, average branching factor ~60" figures, plus a state-space complexity of `5.982483 x 10^22` and a game-tree complexity of `1.371545 x 10^896` for the 7x7 board. **Not peer-reviewed**, and the corresponding section has since been removed from Wikipedia. See 9.2 before citing any of these.

**Written sources**

- [Ataxx - Wikipedia](https://en.wikipedia.org/wiki/Ataxx) - naming, and the 1988 *Infection* origin through to the 1990 Leland arcade release. Note: the current article contains **no** complexity section.
- [Ataxx - Rules (pressibus.org)](http://www.pressibus.org/ataxx/gen/gbregles.html) - clone and jump moves, conversion of all adjacent enemy pieces, forced passing, blocked-square variant, scoring by piece count.
- [Ataxx - igGameCenter](https://www.iggamecenter.com/en/rules/ataxx) - concise standard rule statement; passing notation; game ends when the board is full.
- [Ataxx - GamesCrafters, UC Berkeley](https://gamescrafters.berkeley.edu/site-legacy-archive-sp20/games.php?game=ataxx) - academic treatment of the game.
- [Ataxx (rev 5), Leland Corporation - Internet Archive](https://archive.org/details/arcade_ataxx) - the 1990 arcade original.

---

## 9. Open gaps

Tracked here so nothing is lost between this document and the spec.

**9.1 The termination cutoff (4.6). [RESOLVED]** Confirmed at **30 plies without
progress**, with a **300-ply hard cap** behind it. Both are logged when they fire, so
a too-tight threshold will show up in the results rather than hide in them.

**9.2 Provenance of the `~60` / `~100` figures. [RESOLVED - action required in
PLAN.md]**

Traced. The numbers come from a **complexity section of the Wikipedia article on
Ataxx that no longer exists** - the current article has no such section, and the text
survives only in mirrors of an old revision. That means:

- They are **not peer-reviewed** and carry no primary citation of their own. Citing
  them in an academic report as though they were an established result would be
  indefensible; cite them as an unsourced estimate, or not at all.
- The attribution to a board "with two fixed blocked squares" is **unsupported** -
  the source says a standard 7x7 board. PLAN.md line 58 needs that parenthetical
  removed (see 6.1).

A **genuine peer-reviewed replacement exists** and is now the primary reference:
Ribeiro and Figueiredo, ENIAC 2018 (section 8), which reports *measured* branching
factors on 7x7 Ataxx - ~20 at ply 1, peaking at 92 near ply 25 and ~90 near ply 52.
A copy is archived at [`docs/references/`](../references/). This is strictly better
for our purposes than a single average, because the shape of the curve gives us a
validation target for our own move generator.

The paper is also **directly relevant to the project's research question** - it
evaluates MCTS variants on Ataxx specifically - and should be read in full and cited
in the related-work section, not merely mined for a branching factor. *Note: the
figures above come from the paper's abstract and indexing metadata; the archived PDF
has not yet been read end to end.*

**9.3 Terminal reward scale. [BLOCKING, and shared across all three games]** Ataxx
has a natural margin - the piece difference - so a terminal position can be scored
either as `+1 / 0 / -1` or as something proportional to the margin. The choice is not
cosmetic: MCTS backpropagates the value directly, so margin scoring changes which
moves UCT prefers, while Alpha-Beta's ordering changes too. PLAN.md reports
win/loss/draw rates, which argues for `+1 / 0 / -1` and for keeping the scale
identical across all three games so agent behaviour stays comparable. Needs an
explicit decision in the spec.

**9.4 "Positional stability" in the evaluation function is undefined.** PLAN.md's
starter evaluation for Ataxx is "piece-count difference + number of opponent pieces
immediately convertible by the candidate move + positional stability term". The third
term has no definition, and the Othello intuition does not transfer: **in Ataxx no
piece is ever permanently safe**, because any piece can be converted by an opponent
landing next to it. The usable definition is *exposure*: a piece is vulnerable
exactly when it has at least one empty neighbouring cell, so a natural stability
score counts empty neighbours, negated. Corners have 3 neighbours and edges 5 against
8 for a central cell, which is why corners are structurally safer - the same
conclusion as Othello, but for an entirely different reason. To be fixed in the
evaluation spec.

**9.5 Average branching factor and average game length.** Deliberately deferred - to
be measured by the random agent against the tested implementation, per PLAN.md.
