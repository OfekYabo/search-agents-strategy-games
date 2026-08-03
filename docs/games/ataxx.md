# Gamebook: Ataxx 7x7 (no blocked squares)

> Role in this project: **medium domain** (log10 state space ~ 23.7).
> Status: ruleset **mostly confirmed**; two items in section 4 are flagged as
> **OPEN** and need a decision before implementation.

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

> **Spelling.** PLAN.md and the README currently write "Attax" throughout. That is
> not one of the game's names - it is a typo. It matters because this project imports
> an external complexity figure for the game (average branching factor ~60, average
> game length ~100 plies); a report citing a figure for a game whose name it
> consistently misspells invites doubt about the citation. **Corrected to "Ataxx"
> repo-wide.**

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

**4.4 Passing.** A player with no legal move **must pass**. They do *not* lose.

> PLAN.md line 71 currently states that a player with no legal move loses. **That is
> incorrect** and is corrected here; the sources in section 8 are explicit that
> passing is forced but not losing. This is a substantive rule fix, not a wording
> change: under the erroneous rule a temporarily-boxed-in player loses a game they
> would often go on to win.

**4.5 Terminal conditions.** The game ends as soon as any of these holds:

1. the board is full;
2. a player has zero pieces (that player loses regardless of count);
3. both players pass in succession;
4. the no-progress rule in 4.6 fires. **[OPEN - see below]**

**4.6 Termination, and a problem with the naive ruleset.** *[OPEN - needs decision]*

Rules 1-3 alone **do not guarantee the game ends.** A clone raises the occupied-cell
count by one; a jump leaves it unchanged; conversion leaves it unchanged. So a
sequence consisting only of jumps can continue indefinitely, shuffling pieces back
and forth without ever filling the board. Real Ataxx implementations all impose some
no-progress cutoff; ours must too, or a tournament run can hang forever.

Proposed rule, mirroring the chess 50-move rule:

> Define a ply as **progress** if it is a clone, or if it converted at least one
> opponent piece. If **50 consecutive plies** occur with no progress, the game ends
> and is scored by piece count exactly as in 4.7.

A hard cap (e.g. 400 plies, scored the same way) should sit behind it as a safety net
so no experiment can hang. Both numbers are proposals and need confirmation.

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

**5.2 Branching factor.**

| Quantity | Value | Derivation |
|---|---|---|
| Upper bound | **<= 765** | `45` clone destinations `+ 16 x 45` jump pairs; extremely loose |
| Typical average | **~60** | External reference for canonical Ataxx (see 6.1 for the caveat) |
| Our average | *pending* | To be measured by the random agent against the tested implementation |

The upper bound is of little practical use - it would require every empty cell to be
surrounded by friendly pieces at both distances. The ~60 reference is the number to
reason with, and it is the largest average branching factor of the three games in
this project.

**5.3 Game length.** The canonical reference is ~100 plies average. **There is no
provable maximum** without the rule in 4.6, for the reason given there. With the
proposed rule the hard bound is the cap itself.

**5.4 Note for the report.** Branching factor across the three games is
**not monotonic** in state-space size: Ataxx (~60) is by far the widest, while
Ultimate Tic-Tac-Toe (usually <= 9) has a state space fifteen orders of magnitude
larger. UTTT gets its size from *depth* - up to 81 plies - not width. Any claim in
the report about "harder games" must therefore say which axis it means, because the
two orderings genuinely disagree.

---

## 6. Alternatives considered and rejected

**6.1 Blocked squares.** The arcade original and several implementations support
symmetrically-placed blocked cells, and the ~60 / ~100 reference figure quoted in
PLAN.md is for a 7x7 board *with two blocked squares*. *Rejected:* blocked squares
are an optional variant, they add a board-configuration parameter we have no reason
to vary, and omitting them keeps the `3^49` state-space derivation exact in form.
**The consequence must be stated in the report:** our variant has 49 playable cells
against the reference's 47, so our measured branching factor and game length should
come out slightly *above* ~60 / ~100. The reference is a sanity check on our
measurement, not a target it must match.

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
- The no-progress counter from 4.6 is part of the game state and **must be included
  in the transposition-table key**, otherwise Alpha-Beta can return a cached value
  from a position with a different progress count and mis-evaluate a draw.

---

## 8. References

**Playable reference**

- [Ataxx - onlinesologames.com](https://www.onlinesologames.com/ataxx) - a playable implementation matching our variant: 7x7, corner start, no blocked squares, forced passing, ends when the board fills or a player is eliminated. Useful for getting a feel for the game and for eyeballing our move generator against. Note its jump description ("an L-shaped jump, identical to a knight move in Chess") names only half the legal ring - see 4.1.

**Video explanation**

- *TODO - add a link.* When adding one, note whether it demonstrates the blocked-square variant, since that changes the board from 47 to 49 playable cells (see 6.1).

**Written sources**

- [Ataxx - Wikipedia](https://en.wikipedia.org/wiki/Ataxx) - naming, and the 1988 *Infection* origin through to the 1990 Leland arcade release.
- [Ataxx - Rules (pressibus.org)](http://www.pressibus.org/ataxx/gen/gbregles.html) - clone and jump moves, conversion of all adjacent enemy pieces, forced passing, blocked-square variant, scoring by piece count.
- [Ataxx - igGameCenter](https://www.iggamecenter.com/en/rules/ataxx) - concise standard rule statement; passing notation; game ends when the board is full.
- [Ataxx - GamesCrafters, UC Berkeley](https://gamescrafters.berkeley.edu/site-legacy-archive-sp20/games.php?game=ataxx) - academic treatment of the game.
- [Ataxx (rev 5), Leland Corporation - Internet Archive](https://archive.org/details/arcade_ataxx) - the 1990 arcade original.
