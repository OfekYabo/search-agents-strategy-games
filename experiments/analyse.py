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


def budget_response(rows, budgets):
    # type: (List[Dict[str, Any]], Dict[str, Dict[str, float]]) -> Dict[Any, List[Dict[str, Any]]]
    """Per (game, agent): field score as a function of the time budget.

    Field score, not head-to-head, and deliberately: every agent faces the
    same four-agent pool, so the curves are comparable across agents. The
    head-to-head equivalent is derivable from head_to_head() by reading the
    three configs of one (game, agent, opponent) triple, and storing it twice
    would create two numbers that can disagree.
    """
    table = score_table(rows)
    out = {}
    for (game, config, agent), entry in table.items():
        budget = budgets.get(game, {}).get(config)
        if budget is None:
            continue
        point = {"config": config, "budget_s": budget,
                 "games": entry["games"]}
        point.update(wilson_interval(entry["wins"], entry["draws"],
                                     entry["losses"]))
        out.setdefault((game, agent), []).append(point)
    for points in out.values():
        points.sort(key=lambda p: p["budget_s"])
    return out


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


def budgets_from_games(rows):
    # type: (List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]
    out = {}
    for row in rows:
        out.setdefault(row["game"], {})[row["config"]] = float(
            row["time_budget_s"])
    return out


def join_moves(games_rows, moves_rows):
    # type: (List[Dict[str, Any]], List[Dict[str, Any]]) -> List[Dict[str, Any]]
    """Attach game, config and time_budget_s to each move row.

    Move rows carry only a game_id, so anything grouped by game or config -
    and anything measured against the budget - needs this join first. Orphan
    move rows are dropped rather than raising: the crash-safe logger makes
    them impossible in a completed run, but an analysis should not be the
    thing that fails on a half-written file.
    """
    index = {}
    for row in games_rows:
        index[row["game_id"]] = row
    joined = []
    for move in moves_rows:
        game = index.get(move["game_id"])
        if game is None:
            continue
        merged = dict(move)
        merged["game"] = game["game"]
        merged["config"] = game["config"]
        merged["time_budget_s"] = game["time_budget_s"]
        merged["max_nodes"] = game.get("max_nodes", "")
        merged["max_entries"] = game.get("max_entries", "")
        joined.append(merged)
    return joined



def branching_factor(moves):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Observed legal-action counts from the actual tournament positions.

    The project studies tree width, so the primary branching-factor statistic
    should come from states the evaluated agents actually reached rather than
    only from a separate random-self-play probe.  No extra work is performed
    during search: legal_move_count is already logged for move validation.
    """
    buckets = {}
    for m in moves:
        raw = m.get("legal_move_count", "")
        if raw in (None, ""):
            continue
        key = (m.get("game", ""), m.get("config", ""))
        buckets.setdefault(key, []).append(float(raw))
    out = {}
    for key, values in buckets.items():
        values.sort()
        out[key] = {
            "moves": len(values),
            "mean": sum(values) / len(values),
            "median": _median(values),
            "p95": _percentile(values, 95),
        }
    return out


def branching_factor_by_game(moves):
    # type: (List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]
    """Observed branching factor pooled over budgets, one row per game."""
    buckets = {}
    for m in moves:
        raw = m.get("legal_move_count", "")
        if raw in (None, ""):
            continue
        buckets.setdefault(m.get("game", ""), []).append(float(raw))
    out = {}
    for game, values in buckets.items():
        values.sort()
        out[game] = {
            "moves": len(values),
            "mean": sum(values) / len(values),
            "median": _median(values),
            "p95": _percentile(values, 95),
        }
    return out


def search_throughput(moves):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Search work completed per second, in each agent's native unit.

    Alpha-Beta nodes and MCTS simulations are deliberately never compared as
    the same unit.  The output exposes whichever unit the row actually logs.
    Aggregate throughput uses total work / total elapsed time; the median is
    the typical per-decision throughput and is useful when positions vary
    greatly in cost.
    """
    buckets = {}
    for m in moves:
        elapsed_raw = m.get("elapsed_s", "")
        if elapsed_raw in (None, ""):
            continue
        elapsed = float(elapsed_raw)
        if elapsed <= 0:
            continue
        key = (m.get("game", ""), m.get("config", ""), m.get("agent", ""))
        e = buckets.setdefault(key, {
            "nodes": 0.0, "node_seconds": 0.0, "node_rates": [],
            "simulations": 0.0, "simulation_seconds": 0.0, "simulation_rates": [],
        })
        # Keep the throughput table aligned with the paper's search-effort
        # metrics. Random/one-ply also increment a lightweight node counter,
        # but "nodes/sec" for those baselines is not a tree-search throughput
        # measure and would only add noise to the final tables.
        nodes_raw = m.get("nodes", "")
        if m.get("agent") == "alpha_beta" and nodes_raw not in (None, ""):
            units = float(nodes_raw)
            e["nodes"] += units
            e["node_seconds"] += elapsed
            e["node_rates"].append(units / elapsed)
        sims_raw = m.get("simulations", "")
        if m.get("agent") == "mcts" and sims_raw not in (None, ""):
            units = float(sims_raw)
            e["simulations"] += units
            e["simulation_seconds"] += elapsed
            e["simulation_rates"].append(units / elapsed)
    out = {}
    for key, e in buckets.items():
        row = {}
        if e["node_rates"]:
            rates = sorted(e["node_rates"])
            row.update({
                "nodes_per_second": (e["nodes"] / e["node_seconds"]
                                     if e["node_seconds"] else 0.0),
                "median_nodes_per_second": _median(rates),
                "node_moves": len(rates),
            })
        if e["simulation_rates"]:
            rates = sorted(e["simulation_rates"])
            row.update({
                "simulations_per_second": (
                    e["simulations"] / e["simulation_seconds"]
                    if e["simulation_seconds"] else 0.0),
                "median_simulations_per_second": _median(rates),
                "simulation_moves": len(rates),
            })
        if row:
            out[key] = row
    return out


def search_structure_metrics(moves):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Summarise V3 bounded-memory and reuse instrumentation.

    The two search structures keep their native units. TT entries are never
    converted into MCTS nodes or vice versa; this table is descriptive, not a
    claim that the structures have equal byte cost.
    """
    buckets = {}
    for m in moves:
        key = (m.get("game", ""), m.get("config", ""), m.get("agent", ""))
        e = buckets.setdefault(key, {
            "tt_lookups": 0, "tt_hits": 0, "tt_sizes": [],
            "mcts_tree_nodes": [], "mcts_reused_nodes": [],
            "mcts_reuse_moves": 0, "mcts_moves": 0,
        })

        raw = m.get("tt_lookups", "")
        if raw not in (None, ""):
            e["tt_lookups"] += int(raw)
            e["tt_hits"] += int(m.get("tt_hits") or 0)
            if m.get("tt_size") not in (None, ""):
                e["tt_sizes"].append(int(m["tt_size"]))

        raw = m.get("mcts_tree_nodes", "")
        if raw not in (None, ""):
            e["mcts_moves"] += 1
            e["mcts_tree_nodes"].append(int(raw))
            reused = int(m.get("mcts_reused_nodes") or 0)
            e["mcts_reused_nodes"].append(reused)
            if reused > 0:
                e["mcts_reuse_moves"] += 1

    out = {}
    for key, e in buckets.items():
        if not (e["tt_sizes"] or e["mcts_tree_nodes"]):
            continue
        row = {}
        if e["tt_sizes"]:
            sizes = sorted(e["tt_sizes"])
            row.update({
                "tt_lookups": e["tt_lookups"],
                "tt_hits": e["tt_hits"],
                "tt_hit_rate": (e["tt_hits"] / float(e["tt_lookups"])
                                if e["tt_lookups"] else 0.0),
                "median_tt_size": _median(sizes),
                "max_tt_size": sizes[-1],
            })
        if e["mcts_tree_nodes"]:
            trees = sorted(e["mcts_tree_nodes"])
            reused = sorted(e["mcts_reused_nodes"])
            row.update({
                "median_mcts_tree_nodes": _median(trees),
                "max_mcts_tree_nodes": trees[-1],
                "median_mcts_reused_nodes": _median(reused),
                "mean_mcts_reused_nodes": (sum(reused) / float(len(reused))
                                           if reused else 0.0),
                "total_mcts_reused_nodes": sum(reused),
                "mcts_reuse_moves": e["mcts_reuse_moves"],
                "mcts_reuse_move_pct": (100.0 * e["mcts_reuse_moves"]
                                        / e["mcts_moves"]),
                "mcts_moves": e["mcts_moves"],
            })
        out[key] = row
    return out


def search_time(moves):
    # type: (List[Dict[str, Any]]) -> Dict[Any, Dict[str, Any]]
    """Per (game, config): seconds of search, and share of the whole run.

    This is how long the run took, derived from the data rather than from a
    clock outside it. Summing every move's elapsed_s matched the observed wall
    clock to within 0.1% on both real runs (V1: 7.939 h derived against 7.930 h
    observed; V2: 9.810 h against 9.812 h), because harness overhead is
    negligible - a tournament is essentially all search.

    It is search time, not wall clock, and the difference matters when they
    disagree: a run paused or restarted has a wall clock longer than its search
    time, and the gap is the stall. Compare against run_meta's wall_clock when
    one is recorded.
    """
    seconds = {}
    for m in moves:
        raw = m.get("elapsed_s")
        if raw in (None, ""):
            continue
        key = (m["game"], m["config"])
        seconds[key] = seconds.get(key, 0.0) + float(raw)
    total = sum(seconds.values())
    return dict((key, {"seconds": value,
                       "share": 100.0 * value / total if total else 0.0})
                for key, value in seconds.items())


def roster_from_games(rows):
    # type: (List[Dict[str, Any]]) -> Any
    """Agent hyperparameters, read from the CSV rather than from a metadata
    file or a document.

    Keyed `label@version`, because the whole point is the case a single
    run-level roster cannot express: the same agent label at two versions,
    with different parameters, inside one run. That is exactly what a
    version-comparison run looks like.

    Returns the roster and a sorted list of keys that showed conflicting
    parameters. A conflict means the run is not what it claims to be, so it is
    surfaced rather than resolved by keeping whichever row was read last.
    """
    import json
    roster = {}
    conflicts = set()
    for row in rows:
        for side in ("first", "second"):
            label = row.get("agent_%s" % side)
            if not label:
                continue
            version = row.get("agent_%s_version" % side) or "v1"
            raw = row.get("agent_%s_params" % side)
            if raw in (None, ""):
                continue
            try:
                params = json.loads(raw)
            except ValueError:
                continue
            key = "%s@%s" % (label, version)
            if key in roster and roster[key] != params:
                conflicts.add(key)
            roster[key] = params
    return roster, sorted(conflicts)


def _round(value, places=6):
    # type: (Any, int) -> Any
    """Round floats at write time so platform float repr cannot leak into the
    JSON and break byte-for-byte determinism."""
    if isinstance(value, float):
        return round(value, places)
    if isinstance(value, dict):
        return dict((k, _round(v, places)) for k, v in value.items())
    if isinstance(value, list):
        return [_round(v, places) for v in value]
    return value


def build_analysis(games_rows, moves_rows, label=""):
    # type: (List[Dict[str, Any]], List[Dict[str, Any]], str) -> Dict[str, Any]
    """The single source of truth for the report. Everything is computed here,
    once; report.py renders this and never recomputes."""
    joined = join_moves(games_rows, moves_rows)
    budgets = budgets_from_games(games_rows)

    scores = score_table(games_rows)
    h2h = head_to_head(games_rows)
    sims = simulations_per_root(joined)
    depth = search_depth(joined)
    compliance = budget_compliance(joined)
    lengths = game_length(games_rows)
    tags = tag_distribution(moves_rows)
    response = budget_response(games_rows, budgets)

    agents = sorted(set(
        [r["agent_first"] for r in games_rows]
        + [r["agent_second"] for r in games_rows]))
    roster, roster_conflicts = roster_from_games(games_rows)
    timing = search_time(joined)
    structures = search_structure_metrics(joined)
    branching = branching_factor(joined)
    branching_game = branching_factor_by_game(joined)
    throughput = search_throughput(joined)

    doc = {
        "meta": {
            "label": label,
            "games_total": len(games_rows),
            "games": sorted(budgets),
            "configs": sorted(set(r["config"] for r in games_rows)),
            "agents": agents,
            "budgets": budgets,
            "experiments": sorted(set(
                r.get("experiment") or "legacy" for r in games_rows)),
            "agent_versions": sorted(set(
                [r.get("agent_first_version") or "v1" for r in games_rows]
                + [r.get("agent_second_version") or "v1"
                   for r in games_rows])),
            "roster": roster,
            "roster_conflicts": roster_conflicts,
            "total_search_seconds": sum(
                e["seconds"] for e in timing.values()),
        },
        "score_table": [
            dict(zip(("game", "config", "agent"), key),
                 wins=e["wins"], draws=e["draws"], losses=e["losses"],
                 **wilson_interval(e["wins"], e["draws"], e["losses"]))
            for key, e in sorted(scores.items())],
        "head_to_head": [
            dict(zip(("game", "config", "agent", "opponent"), key), **e)
            for key, e in sorted(h2h.items())],
        "budget_response": [
            {"game": key[0], "agent": key[1], "points": points}
            for key, points in sorted(response.items())],
        "simulations_per_root": [
            dict(zip(("game", "config", "agent"), key),
                 verdict=_verdict(e["median_per_root"]), **e)
            for key, e in sorted(sims.items())],
        "search_depth": [
            dict(zip(("game", "config", "agent"), key), **e)
            for key, e in sorted(depth.items())],
        "budget_compliance": [
            dict(zip(("game", "config", "agent"), key), **e)
            for key, e in sorted(compliance.items())],
        "search_time": [
            dict(zip(("game", "config"), key), **e)
            for key, e in sorted(timing.items())],
        "game_length": [
            dict(zip(("game", "config"), key), **e)
            for key, e in sorted(lengths.items())],
        "tag_distribution": [
            {"agent": key[0], "tag": key[1], "count": count}
            for key, count in sorted(tags.items())],
        "search_structure_metrics": [
            dict(zip(("game", "config", "agent"), key), **e)
            for key, e in sorted(structures.items())],
        "branching_factor": [
            dict(zip(("game", "config"), key), **e)
            for key, e in sorted(branching.items())],
        "branching_factor_by_game": [
            dict(game=game, **e) for game, e in sorted(branching_game.items())],
        "search_throughput": [
            dict(zip(("game", "config", "agent"), key), **e)
            for key, e in sorted(throughput.items())],
        "first_move_advantage": first_move_advantage(games_rows),
    }
    return _round(doc)


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
    # There is deliberately no --out here. It existed, defaulted to
    # results/figures, and was never read - figures were intended from the
    # start and never built. Figure output belongs to report.py, and two
    # modules with an --out meaning different things is worse than none.
    parser.add_argument("--json", default="")
    parser.add_argument("--label", default="")
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

    if args.json:
        import json
        document = build_analysis(clean, moves, label=args.label)
        directory = os.path.dirname(args.json)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(args.json, "w") as handle:
            json.dump(document, handle, sort_keys=True, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
