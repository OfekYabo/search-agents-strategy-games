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

# Below this many simulations per root move MCTS cannot try every candidate
# once, so a result there describes the budget rather than the algorithm.
# docs/spec/technical-spec.md section 5.5.
VIABILITY_FLOOR = 10.0


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


def wilson_interval(wins, draws, losses, z=1.96):
    # type: (int, int, int, float) -> Dict[str, float]
    """Wilson score interval for the score rate, draws counting as half a win.

    Not the normal approximation. At the rates this study actually produces -
    Ataxx MCTS scored 2-0-38 against the heuristic - the normal approximation
    returns a lower bound of -0.018, which is not a reportable quantity. Wilson
    is closed-form, needs only `math`, and stays inside [0, 1] at the extremes
    where the interesting results live.
    """
    n = wins + draws + losses
    if n <= 0:
        return {"score": 0.0, "ci_low": 0.0, "ci_high": 0.0, "games": 0}
    p = (wins + 0.5 * draws) / float(n)
    z2 = z * z
    denominator = 1.0 + z2 / n
    centre = p + z2 / (2.0 * n)
    margin = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n))
    return {"score": p,
            "ci_low": max(0.0, (centre - margin) / denominator),
            "ci_high": min(1.0, (centre + margin) / denominator),
            "games": n}


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


def head_to_head(rows):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Per (game, config, agent, opponent): record and score, pooled over both
    seat orders.

    The score_table figure is against the whole four-agent field, which
    conflates opponents - MCTS's 0.483 on Ataxx-easy averages 1.000 against
    the random agent with 0.000 against Alpha-Beta. Every claim the project
    actually makes is a head-to-head claim, so it needs its own table.
    """
    table = {}
    for row in rows:
        first, second = row["agent_first"], row["agent_second"]
        if first == second:
            continue
        for agent, opponent, seat in ((first, second, "first"),
                                      (second, first, "second")):
            key = (row["game"], row["config"], agent, opponent)
            e = table.setdefault(key, {"wins": 0, "draws": 0, "losses": 0})
            if row["winner"] == "draw":
                e["draws"] += 1
            elif row["winner"] == seat:
                e["wins"] += 1
            else:
                e["losses"] += 1
    for e in table.values():
        e.update(wilson_interval(e["wins"], e["draws"], e["losses"]))
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
    node is not the same unit of work as a rollout.

    The headline is the MEDIAN of each row's own simulations/legal_move_count
    ratio, not the mean of those ratios, and not the ratio of the means.

    The mean of the ratios is unusable here and an earlier version of this
    function used it. A position with a single legal move contributes a ratio
    equal to the whole simulation count - tens of thousands - even though no
    search decision was made there at all. On the real run 10-14% of Ataxx
    MCTS decisions and 20-25% of Isolation ones have exactly one legal move,
    and they inflated the reported figure by 4-8x, enough to move Ataxx-hard
    across the ample threshold. The ratio of the means has the opposite bias:
    it weights each decision by its branching factor, so it under-reports
    exactly the low-width endgame positions.

    The median describes a typical decision under either skew. Because the
    spec's floor is a property of each decision rather than of the average,
    p5_per_root and pct_below_floor are reported beside it - a config can
    average comfortably and still spend a fifth of its decisions unable to
    try every candidate once.
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
        acc = sums.setdefault(key, {"sim_total": 0.0, "ratios": []})
        acc["sim_total"] += simulations
        acc["ratios"].append(simulations / legal_count)
    table = {}
    for key, acc in sums.items():
        ratios = sorted(acc["ratios"])
        n = len(ratios)
        below = sum(1 for r in ratios if r < VIABILITY_FLOOR)
        table[key] = {
            "moves": n,
            "mean_simulations": acc["sim_total"] / n if n else 0.0,
            "median_per_root": _median(ratios),
            "mean_per_root": sum(ratios) / n if n else 0.0,
            "p5_per_root": _percentile(ratios, 5),
            "pct_below_floor": 100.0 * below / n if n else 0.0,
        }
    return table


def _median(sorted_values):
    # type: (List[float]) -> float
    n = len(sorted_values)
    if not n:
        return 0.0
    middle = n // 2
    if n % 2:
        return sorted_values[middle]
    return (sorted_values[middle - 1] + sorted_values[middle]) / 2.0


def _percentile(sorted_values, pct):
    # type: (List[float], float) -> float
    """Nearest-rank percentile. Used for the low tail, where the question is
    'how bad did the worst decisions get', so rounding toward the worse
    observation is the conservative direction."""
    if not sorted_values:
        return 0.0
    index = int(pct / 100.0 * len(sorted_values))
    return sorted_values[min(index, len(sorted_values) - 1)]


def search_depth(moves):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Per (game, config, agent): depth reached. Alpha-Beta only in practice,
    since only it records a depth - MCTS's tree has no single depth."""
    buckets = {}
    for m in moves:
        raw = m.get("depth", "")
        if raw in (None, ""):
            continue
        key = (m["game"], m["config"], m["agent"])
        buckets.setdefault(key, []).append(int(raw))
    table = {}
    for key, values in buckets.items():
        values.sort()
        table[key] = {"median_depth": _median(values),
                      "max_depth": values[-1],
                      "moves": len(values)}
    return table


def budget_compliance(moves):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Per (game, config, agent): elapsed time as a fraction of the budget.

    This is instrument validation, not a result. A wall-clock budget that the
    agents systematically overrun would make every comparison in the study
    describe the overrun rather than the algorithms.
    """
    buckets = {}
    for m in moves:
        budget = float(m.get("time_budget_s") or 0.0)
        if budget <= 0:
            continue
        key = (m["game"], m["config"], m["agent"])
        buckets.setdefault(key, []).append(float(m["elapsed_s"]) / budget)
    table = {}
    for key, values in buckets.items():
        values.sort()
        table[key] = {"mean_ratio": sum(values) / len(values),
                      "p99_ratio": _percentile(values, 99),
                      "max_ratio": values[-1],
                      "moves": len(values)}
    return table


def game_length(rows):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Per (game, config): game length in plies and the end-reason split.

    Agent play and random self-play give very different lengths, and the
    original runtime estimate for the tournament was wrong by 2.5x because it
    used the random-play figure. Keyed by config as well as game because the
    budget changes how long games run, and a single per-game figure hides it.
    """
    buckets = {}
    for row in rows:
        key = (row["game"], row["config"])
        e = buckets.setdefault(key, {"plies": [], "end_reasons": {}})
        e["plies"].append(int(row["plies"]))
        reason = row["end_reason"]
        e["end_reasons"][reason] = e["end_reasons"].get(reason, 0) + 1
    table = {}
    for key, e in buckets.items():
        plies = sorted(e["plies"])
        table[key] = {"mean_plies": sum(plies) / float(len(plies)),
                      "median_plies": _median(plies),
                      "games": len(plies),
                      "end_reasons": e["end_reasons"]}
    return table


def _verdict(per_root):
    # type: (float) -> str
    """Below roughly 10 simulations per root move, MCTS is not meaningfully
    searching. Thresholds per the spec: ample >= 30, viable >= 10, thin >= 3,
    STARVED below that. Feed this the median, not the mean - see
    simulations_per_root."""
    if per_root >= 30:
        return "ample"
    if per_root >= VIABILITY_FLOOR:
        return "viable"
    if per_root >= 3:
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
    print("\n| game | config | agent | mean sims | median /root | p5 /root "
          "| %% below %d | verdict |" % int(VIABILITY_FLOOR))
    print("|---|---|---|---|---|---|---|---|")
    sims = simulations_per_root(joined_moves)
    for key in sorted(sims):
        e = sims[key]
        print("| %s | %s | %s | %.1f | %.1f | %.1f | %.1f%% | %s |"
              % (key[0], key[1], key[2], e["mean_simulations"],
                 e["median_per_root"], e["p5_per_root"],
                 e["pct_below_floor"], _verdict(e["median_per_root"])))
    print("\nA STARVED row means the budget, not the algorithm, is what the "
          "result describes.")
    print("\nThe headline is the MEDIAN of the per-decision "
          "simulations/legal-moves ratio. The mean of that ratio is not "
          "reported because positions with a single legal move contribute a "
          "ratio equal to the entire simulation count and inflate it by 4-8x; "
          "`p5 /root` and `%% below %d` are given because the viability floor "
          "is a property of each decision, not of the average."
          % int(VIABILITY_FLOOR))
    return 0


if __name__ == "__main__":
    sys.exit(main())
