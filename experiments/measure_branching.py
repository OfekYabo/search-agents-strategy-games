"""Measure branching factor per ply and game length by random self-play.

This is the project's primary move-generator validation. For Ataxx the measured
curve is compared against Ribeiro and Figueiredo (ENIAC 2018): roughly 20 at ply
1, peaking near 92 around ply 25. Reproducing that double-humped shape is strong
evidence the generator is right; a flat curve indicates a bug, most likely the
eight knight-shaped jump destinations.

Run directly for a per-ply table:  python3 -m experiments.measure_branching
"""
import random
import statistics
from dataclasses import dataclass
from typing import Any, List


@dataclass(frozen=True)
class BranchingStats:
    game: str
    n_games: int
    mean: float
    median: float
    max_b: int
    mean_by_ply: List[float]
    mean_length: float


def measure(game, n_games=200, seed=0, max_plies=400):
    # type: (Any, int, int, int) -> BranchingStats
    """Play n_games random games, recording the legal-move count at every ply."""
    rng = random.Random(seed)
    all_counts = []          # type: List[int]
    by_ply = []              # type: List[List[int]]
    lengths = []             # type: List[int]

    for _ in range(n_games):
        state = game.initial_state()
        ply = 0
        while ply < max_plies:
            moves = game.legal_moves(state)
            if not moves:
                break
            count = len(moves)
            all_counts.append(count)
            while len(by_ply) <= ply:
                by_ply.append([])
            by_ply[ply].append(count)
            state = game.apply_move(state, rng.choice(moves))
            ply += 1
        lengths.append(ply)

    return BranchingStats(
        game=game.NAME,
        n_games=n_games,
        mean=statistics.mean(all_counts),
        median=statistics.median(all_counts),
        max_b=max(all_counts),
        mean_by_ply=[statistics.mean(counts) for counts in by_ply],
        mean_length=statistics.mean(lengths),
    )


def _report(stats, reference=None):
    # type: (BranchingStats, Any) -> None
    print("\n=== %s (%d random games) ===" % (stats.game, stats.n_games))
    print("  mean b %.2f | median b %.1f | max b %d | mean length %.1f plies"
          % (stats.mean, stats.median, stats.max_b, stats.mean_length))
    peak = max(stats.mean_by_ply)
    print("  ply-1 b %.1f | peak b %.1f at ply %d"
          % (stats.mean_by_ply[0], peak, stats.mean_by_ply.index(peak)))
    if reference:
        print("  reference: %s" % reference)
    step = max(1, len(stats.mean_by_ply) // 25)
    cells = ["%d:%.0f" % (p, stats.mean_by_ply[p])
             for p in range(0, len(stats.mean_by_ply), step)]
    print("  by ply -> " + "  ".join(cells))


def main():
    from games import ataxx, isolation, uttt
    _report(measure(isolation, n_games=500, seed=1),
            "derived: 11 at ply 1, max 16, at most 23 plies")
    _report(measure(uttt, n_games=300, seed=2),
            "derived: 81 at ply 1, at most 81 plies")
    _report(measure(ataxx, n_games=200, seed=3),
            "Ribeiro and Figueiredo 2018: ~20 at ply 1, peak ~92 near ply 25, "
            "~100 plies average (on 47 playable cells; ours has 49)")


if __name__ == "__main__":
    main()
