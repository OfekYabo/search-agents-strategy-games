"""Tables and figures, computed only from the CSVs.

Reporting rules from the spec, all load-bearing:
  - Report score rate (W + 0.5D)/N AND the win/draw/loss split. Never "win rate"
    alone: a draw-heavy result is itself a finding and score rate hides it.
  - Run the first-move binomial test on DECISIVE games only, since a 50/50 null
    is undefined when draws exist, and report how many draws were excluded.
  - Exclude error-tagged moves and their games from all statistics, and report
    the counts separately. A nonzero error count is a bug report, not a datum.
  - Report simulations per root move beside every MCTS result. Below about 10,
    MCTS is not meaningfully searching and any conclusion describes the budget.
"""
import argparse
import csv
import math
import os
import sys
from typing import Any, Dict, List


def load(games_csv, moves_csv):
    with open(games_csv, newline="") as h:
        games = list(csv.DictReader(h))
    with open(moves_csv, newline="") as h:
        moves = list(csv.DictReader(h))
    return games, moves


def binomial_p(wins, n):
    # type: (int, int) -> float
    """Two-sided exact binomial test against p=0.5. Stdlib only.

    Computed in log space via lgamma. The naive form - summing binomial
    coefficients and dividing by 2**n - overflows: the full grid is over two
    thousand games, and float(2 ** 2000) raises OverflowError.
    """
    if n <= 0:
        return 1.0
    observed = abs(wins - n / 2.0)
    log_half_n = -n * math.log(2.0)
    total = 0.0
    for k in range(n + 1):
        if abs(k - n / 2.0) >= observed:
            log_coeff = (math.lgamma(n + 1) - math.lgamma(k + 1)
                         - math.lgamma(n - k + 1))
            total += math.exp(log_coeff + log_half_n)
    return min(1.0, total)


def score_table(rows):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Per (game, config, agent): wins, draws, losses and score rate.

    Each row contributes to both seats, so an agent's record is pooled across
    the seat it happened to occupy.
    """
    table = {}
    for row in rows:
        for seat, agent in (("first", row["agent_first"]),
                            ("second", row["agent_second"])):
            key = (row["game"], row["config"], agent)
            e = table.setdefault(key, {"wins": 0, "draws": 0, "losses": 0})
            if row["winner"] == "draw":
                e["draws"] += 1
            elif row["winner"] == seat:
                e["wins"] += 1
            else:
                e["losses"] += 1
    for e in table.values():
        n = e["wins"] + e["draws"] + e["losses"]
        e["games"] = n
        e["score"] = (e["wins"] + 0.5 * e["draws"]) / float(n) if n else 0.0
    return table


def tag_distribution(moves):
    out = {}
    for m in moves:
        key = (m["agent"], m["tag"])
        out[key] = out.get(key, 0) + 1
    return out


def simulations_per_root(moves):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Per (game, config, agent): mean simulations and mean simulations per
    legal root move.

    Below roughly 10 simulations per root move, MCTS cannot try each candidate
    even once, so any conclusion drawn about it there describes the budget
    rather than the algorithm. Reported beside every MCTS result for exactly
    that reason.

    Rows with no simulations value are skipped - that is every Alpha-Beta
    row, since nodes and rollouts are deliberately separate columns and a
    node is not the same unit of work as a rollout. mean_per_root is the
    mean of each row's own simulations/legal_move_count ratio, not the ratio
    of the means: averaging the ratios first, then across rows, keeps a
    position with few legal moves from flattering the overall mean the way
    summing simulations and legal counts separately would.
    """
    sums = {}
    for m in moves:
        sim_raw = m.get("simulations", "")
        legal_raw = m.get("legal_move_count", "")
        if sim_raw in (None, "") or legal_raw in (None, ""):
            continue
        simulations = float(sim_raw)
        legal_count = float(legal_raw)
        if legal_count <= 0:
            continue
        key = (m["game"], m["config"], m["agent"])
        acc = sums.setdefault(key, {"sim_total": 0.0, "ratio_total": 0.0,
                                     "n": 0})
        acc["sim_total"] += simulations
        acc["ratio_total"] += simulations / legal_count
        acc["n"] += 1
    table = {}
    for key, acc in sums.items():
        n = acc["n"]
        table[key] = {
            "moves": n,
            "mean_simulations": acc["sim_total"] / n if n else 0.0,
            "mean_per_root": acc["ratio_total"] / n if n else 0.0,
        }
    return table


def _verdict(mean_per_root):
    # type: (float) -> str
    """Below roughly 10 simulations per root move, MCTS is not meaningfully
    searching. Thresholds per the spec: ample >= 30, viable >= 10, thin >= 3,
    STARVED below that."""
    if mean_per_root >= 30:
        return "ample"
    if mean_per_root >= 10:
        return "viable"
    if mean_per_root >= 3:
        return "thin"
    return "STARVED"


def first_move_advantage(rows):
    # type: (List[Dict[str, Any]]) -> Dict[str, Any]
    first = sum(1 for r in rows if r["winner"] == "first")
    second = sum(1 for r in rows if r["winner"] == "second")
    draws = sum(1 for r in rows if r["winner"] == "draw")
    decisive = first + second
    return {"first": first, "second": second, "decisive": decisive,
            "excluded_draws": draws,
            "p": binomial_p(first, decisive) if decisive else 1.0}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", default="results/raw")
    parser.add_argument("--out", default="results/figures")
    args = parser.parse_args(argv)

    games, moves = load(os.path.join(args.raw, "games.csv"),
                        os.path.join(args.raw, "moves.csv"))

    errors = [m for m in moves if m["tag"] == "error"]
    bad_games = set(m["game_id"] for m in errors)
    clean = [g for g in games if g["game_id"] not in bad_games]
    print("games %d (excluded %d containing %d error moves)"
          % (len(clean), len(games) - len(clean), len(errors)))
    if errors:
        print("  NOTE: a nonzero error count is a bug report, not a data point.")

    table = score_table(clean)
    print("\n## Score rate by agent")
    print("\n| game | config | agent | W | D | L | score |")
    print("|---|---|---|---|---|---|---|")
    for key in sorted(table):
        e = table[key]
        print("| %s | %s | %s | %d | %d | %d | %.3f |"
              % (key[0], key[1], key[2], e["wins"], e["draws"], e["losses"],
                 e["score"]))

    print("\n## First-move advantage (decisive games only)")
    fm = first_move_advantage(clean)
    print("first %d, second %d, decisive %d, draws excluded %d, p = %.4f"
          % (fm["first"], fm["second"], fm["decisive"],
             fm["excluded_draws"], fm["p"]))

    print("\n## Move-tag distribution")
    clean_moves = [m for m in moves if m["game_id"] not in bad_games]
    tags = tag_distribution(clean_moves)
    for key in sorted(tags):
        print("  %-12s %-16s %d" % (key[0], key[1], tags[key]))

    # moves.csv carries only game_id, not game/config - join against the
    # (already error-filtered) games rows to get the (game, config) key that
    # simulations_per_root groups by.
    game_info = dict((g["game_id"], (g["game"], g["config"])) for g in clean)
    joined_moves = []
    for m in clean_moves:
        info = game_info.get(m["game_id"])
        if info is None:
            continue
        merged = dict(m)
        merged["game"], merged["config"] = info
        joined_moves.append(merged)

    print("\n## Simulations per root move (MCTS)")
    print("\n| game | config | agent | mean sims | per root move | verdict |")
    print("|---|---|---|---|---|---|")
    sims = simulations_per_root(joined_moves)
    for key in sorted(sims):
        e = sims[key]
        print("| %s | %s | %s | %.1f | %.1f | %s |"
              % (key[0], key[1], key[2], e["mean_simulations"],
                 e["mean_per_root"], _verdict(e["mean_per_root"])))
    print("\nA STARVED row means the budget, not the algorithm, is what the "
          "result describes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
