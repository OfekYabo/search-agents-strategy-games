# Gamebook: Ultimate Tic-Tac-Toe

> Role in this project: **large domain** (log10 state space ~ 38.9, or ~39.9 under
> the corrected bound in section 5.1).
> Status: ruleset **mostly confirmed**; one item in section 4 is flagged as **OPEN**
> and needs a decision before implementation.

---

## 1. Provenance

Ultimate Tic-Tac-Toe (also seen as "super", "meta", or "nine-board" tic-tac-toe) has
no single publisher and no single canonical rulebook. It circulates as a folk game
with a stable core - nine 3x3 local boards inside a 3x3 global board, and a move
sends the opponent to the correspondingly-positioned local board - and **unstable
edges**, chiefly around what happens to boards that are already decided.

That instability is the reason this document exists. Two implementations can both
call themselves Ultimate Tic-Tac-Toe and disagree about legal moves. Section 4 pins
down our reading; section 6 records the alternatives.

---

## 2. Board and notation

Nine **local boards** arranged in a 3x3 **global board**. Both are indexed `0..8` in
reading order:

```
   global board          cell index within
   (local board id)      each local board

    0 | 1 | 2             0 | 1 | 2
   ---+---+---           ---+---+---
    3 | 4 | 5             3 | 4 | 5
   ---+---+---           ---+---+---
    6 | 7 | 8             6 | 7 | 8
```

A move is a pair `(b, c)`: play in local board `b`, cell `c`. Because both indexings
use the same 0..8 scheme, the send rule is simply "your cell index becomes their
board index".

Each local board has a status: **undecided**, **won by P1**, **won by P2**, or
**drawn**.

---

## 3. Starting position

All 81 cells empty, all nine local boards undecided, no send constraint in force.
**Player 1 moves first and may play any of the 81 cells.**

---

## 4. Rules of play

**4.1 The send rule.** After a move at `(b, c)`, the opponent must play in local
board `c`.

**4.2 The free-choice exception.** If local board `c` is **not undecided** - that is,
it has been won by either player or has been drawn - the send constraint is void and
the opponent may play in **any undecided local board**.

**4.3 Decided boards are closed.** *[OPEN - needs decision]* Once a local board is
won or drawn, **no further moves may be played in it**, even if it still has empty
cells. Its remaining empty cells are dead for the rest of the game.

> This is the one genuinely contested rule in the game and the sources disagree by
> omission - they state the free-choice exception clearly but do not say whether the
> won board's leftover cells stay playable. See 6.1 for the alternative and the
> argument. Our reading is the one used by most bot implementations, and it is
> self-consistent with 4.2: if a decided board were still playable, sending an
> opponent there would not need an exception at all.

**4.4 Winning a local board.** Three of your marks in a row - horizontally,
vertically, or diagonally - wins that local board immediately.

**4.5 Drawing a local board.** A local board that becomes full with no three-in-a-row
is **drawn**. A drawn board **counts for neither player** and can never form part of
any global line.

**4.6 Winning the game.** Three local boards won by the same player, in a row on the
global board, wins the game immediately - checked as soon as a local board is won.

**4.7 Drawing the game.** If no legal move exists - every local board is decided -
and no player holds a global line, the game is a **draw**. Draws are a normal,
frequent outcome here and the tournament logging must treat them as a first-class
result, unlike Isolation where they cannot occur.

---

## 5. Derived properties

**5.1 State-space upper bound.** PLAN.md currently gives:

```
2  x  3^81  =  2 x 4.44 x 10^38  ~  8.89 x 10^38          log10 = 38.9
```

**This omits part of the state.** Which local board the player to move is sent to is
not derivable from the cell contents alone - two identical-looking positions can have
different legal moves - so the send constraint is a genuine state component, with 10
values (nine boards, or unconstrained):

```
2  x  10  x  3^81  ~  8.89 x 10^39                        log10 = 39.9
```

Recommendation: **adopt the second form**, showing this derivation. It is more
defensible under questioning, and it barely moves the narrative - the project's span
goes from ~28.9 to ~29.9 orders of magnitude. Both are loose upper bounds; neither
excludes unreachable configurations, of which there are very many (for instance any
position where both players hold a completed line).

**5.2 Branching factor.** This is where PLAN.md's "common case bounded by 9" needs
care:

| Situation | Branching factor |
|---|---|
| Ply 1 | **81** |
| Sent to an undecided board (the usual case) | **<= 9**, and falls as that board fills |
| Free choice (sent to a decided board) | **all empty cells in all undecided boards** - up to ~70 early on |
| Average over a game | *pending* - to be measured by the random agent |

The free-choice case cannot arise before ply 5, since a local board needs at least
three of one player's marks to be won. It becomes common in the middle game, and it
produces branching-factor spikes far above 9. A search implementation that assumes a
hard cap of 9 will be wrong.

**5.3 Game length.** Exactly one cell is filled per ply and no cell is ever vacated,
so the game lasts **at most 81 plies**. Under 4.3 it usually ends well short of that,
because cells inside decided boards are abandoned. The average is *pending*
measurement.

**5.4 Note for the report.** UTTT has by far the largest state space of the three
games and by far the *smallest* typical branching factor. Its size comes from
**depth** - up to 81 plies - not width. This is the cleanest illustration in the
project that "state-space size" and "search difficulty" are different axes, and it
should be expected to affect the two paradigms differently: deep-and-narrow suits
iterative-deepening Alpha-Beta, whereas MCTS's advantage usually shows up in
wide-and-shallow domains like Ataxx.

---

## 6. Alternatives considered and rejected

**6.1 Decided boards remain playable.** Under this reading, a won local board keeps
its empty cells in play; moves there simply cannot change its owner, and being sent
to one is legal and unremarkable. *Rejected*, for two reasons. First, it makes the
free-choice rule in 4.2 redundant for won boards, yet every source states that rule
prominently - which only makes sense if such boards are closed. Second, it lets
players make null moves inside dead boards purely to control where the opponent is
sent, which changes the strategic character of the game substantially. This is a
real fork in the rules, though, and the report should name which side it took.

**6.2 Free choice only on a *full* board, not a won one.** A middle reading: you are
sent to a won-but-not-full board and must play there. *Rejected:* the sources
consistently group won and drawn boards together when stating the exception.

**6.3 A drawn local board counts for both players** (some house rules let a tied
board count toward either player's global line). *Rejected:* the sources state
explicitly that a tie forms part of no three-in-a-row, and counting it for both
would allow both players to hold a winning line at once.

**6.4 Global win by majority of local boards** when the board fills without a line.
*Rejected:* not part of the standard rules; 4.7's draw is the standard outcome, and
draws are analytically useful to us as a distinct result to log.

**6.5 Keeping PLAN.md's `2 x 3^81` state-space bound.** *Rejected* in favour of 5.1's
corrected form, which accounts for the send constraint - though the choice is
cosmetic, since both are loose upper bounds.

---

## 7. Implementation notes

- State: 81 cell values, 9 local-board statuses, the send constraint (`0..8` or
  "free"), and the side to move. The local-board statuses are derived data, but
  caching them is worthwhile - they are read on every move generation.
- The send constraint **must be part of the transposition-table key**. Two positions
  with identical cells but different send constraints have different legal moves and
  different values; conflating them corrupts the table.
- Check the global win only after a local board's status changes to *won*. Checking
  every ply is wasted work.
- Precompute the eight winning lines as index triples and reuse the same table for
  local and global boards - they are structurally identical.
- Move generation has exactly two paths (constrained and free). Both must skip
  decided boards, per 4.3.

---

## 8. References

- [Ultimate Tic-Tac-Toe Rules - tictactoefree.com](https://tictactoefree.com/ultimate-tic-tac-toe/rules) - the send rule; free choice when sent to a board already won *or* tied; a tied local board forms part of no three-in-a-row; overall draw when no global line is made.
- [Tic-tac-toe variants - Wikipedia](https://en.wikipedia.org/wiki/Tic-tac-toe_variants) - structural definition of the nine-board game.
- [Ultimate Tic-Tac-Toe - BoardGameGeek](https://boardgamegeek.com/boardgame/42336/ultimate-tic-tac-toe) - game entry and rule discussion.
- [Ultimate Tic-Tac-Toe (printable rules, PDF)](https://www.thepaintedturtle.org/sites/main/files/file-attachments/ultimate_tic-tac-toe_instructions_0.pdf) - independent statement of the same core rules.
