"""Figures for the version duel.

Three, each earning its place by showing something a table states poorly:

  fig-duel-budget    the headline. v3's score against budget, per agent, per
                     game. The Ataxx panel is the study's sharpest result -
                     two agents crossing in opposite directions - and a table
                     of nine numbers does not make a crossing visible.
  fig-duel-forest    all 27 cells with their intervals against the 0.500 null.
                     A forest plot is the standard way to show many effect
                     sizes at once, and it makes "mostly unresolved, three
                     clearly not" legible at a glance.
  fig-duel-work      work gained against strength gained. The one that carries
                     F3: the agent that gained 8% more work won, the agent that
                     gained 100% lost.

Determinism comes from importing experiments.figures, which pins the Agg
backend and the SVG hashsalt. Without that, matplotlib stamps a date into the
SVG and salts element ids per process, and two identical runs produce different
bytes while looking identical.
"""
import os

from experiments import figures          # noqa: F401  (pins Agg + hashsalt)
from experiments.analyse import wilson_interval
from experiments.duel_report import score_for

import matplotlib.pyplot as plt          # noqa: E402  (must follow the pin)

_SAVE = {"format": "svg", "metadata": {"Date": None}, "bbox_inches": "tight"}
_AGENT_ORDER = ("alpha_beta", "mcts", "heuristic")
_COLOURS = {"alpha_beta": "#1f77b4", "mcts": "#d62728", "heuristic": "#2ca02c"}
_NULL = 0.500


def _budgets(games):
    # type: (list) -> dict
    out = {}
    for row in games:
        out.setdefault(row["game"], {})[row["config"]] = float(
            row["time_budget_s"])
    return out


def _save(fig, out_dir, name):
    path = os.path.join(out_dir, name)
    fig.savefig(path, **_SAVE)
    plt.close(fig)
    return path


def _agents_present(games):
    present = {r["agent"] for r in games}
    return [a for a in _AGENT_ORDER if a in present]


def _budget_figure(games, meta, out_dir):
    new = (meta.get("versions") or ["v2", "v3"])[1]
    cells = score_for(games, new, ("agent", "game", "config"))
    budgets = _budgets(games)
    game_names = sorted(budgets)
    agents = _agents_present(games)

    fig, axes = plt.subplots(1, len(game_names),
                             figsize=(4.6 * len(game_names), 4.2),
                             squeeze=False, sharey=True)
    for column, game in enumerate(game_names):
        ax = axes[0][column]
        configs = sorted(budgets[game], key=lambda c: budgets[game][c])
        # Exactly-overlapping series are common here and are the point: where
        # v3 equals v2 the score is exactly 0.500 for every agent. Drawn raw,
        # the last series painted hides the others and a reader concludes an
        # agent is missing. A small multiplicative dodge on the log x axis
        # separates them without moving any point off its budget.
        for offset, agent in enumerate(agents):
            dodge = 1.0 + (offset - (len(agents) - 1) / 2.0) * 0.045
            xs, ys, lo, hi = [], [], [], []
            for config in configs:
                entry = cells.get((agent, game, config))
                if entry is None:
                    continue
                xs.append(budgets[game][config] * dodge)
                ys.append(entry["score"])
                lo.append(entry["score"] - entry["ci_low"])
                hi.append(entry["ci_high"] - entry["score"])
            if not xs:
                continue
            ax.errorbar(xs, ys, yerr=[lo, hi], marker="o", capsize=3,
                        label=agent, color=_COLOURS.get(agent))
        ax.axhline(_NULL, linestyle="--", linewidth=1, color="grey")
        ax.set_xscale("log")
        ax.set_ylim(0, 1)
        ax.set_title(game)
        ax.set_xlabel("budget (s, log)")
        if column == 0:
            ax.set_ylabel("%s score vs the older version" % new)
            ax.legend(fontsize="small", loc="lower left")
    fig.suptitle("Does the newer version win, and does that change with "
                 "budget?  (0.500 = indistinguishable)")
    return _save(fig, out_dir, "fig-duel-budget.svg")


def _forest_figure(games, meta, out_dir):
    new = (meta.get("versions") or ["v2", "v3"])[1]
    cells = score_for(games, new, ("agent", "game", "config"))
    budgets = _budgets(games)

    rows = []
    for agent in _agents_present(games):
        for game in sorted(budgets):
            for config in sorted(budgets[game],
                                 key=lambda c: budgets[game][c]):
                entry = cells.get((agent, game, config))
                if entry is not None:
                    rows.append(("%s / %s / %s" % (agent, game, config),
                                 agent, entry))
    rows.reverse()          # first row at the top of the axis

    fig, ax = plt.subplots(figsize=(7.5, 0.30 * len(rows) + 1.6))
    for index, (label, agent, entry) in enumerate(rows):
        resolved = entry["ci_low"] > _NULL or entry["ci_high"] < _NULL
        ax.errorbar(entry["score"], index,
                    xerr=[[entry["score"] - entry["ci_low"]],
                          [entry["ci_high"] - entry["score"]]],
                    fmt="o", capsize=3, color=_COLOURS.get(agent),
                    alpha=1.0 if resolved else 0.45,
                    markersize=6 if resolved else 4)
    ax.axvline(_NULL, linestyle="--", linewidth=1, color="grey")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize="small")
    ax.set_xlim(0, 1)
    ax.set_xlabel("%s score vs the older version, 95%% interval" % new)
    ax.set_title("Every cell against the 0.500 null\n"
                 "(faded = interval contains 0.500, i.e. not resolved)",
                 fontsize="medium")
    return _save(fig, out_dir, "fig-duel-forest.svg")


def work_ratios(games, moves):
    # type: (list, list) -> dict
    """Per (agent, game, config): median work per move for each version.

    Work is nodes for Alpha-Beta and simulations for MCTS - deliberately not
    combined into one number, since a node and a rollout are not the same unit
    of effort. The ratio between two versions of the *same* agent is
    meaningful; a ratio across agents would not be.
    """
    index = dict((r["game_id"], r) for r in games if r.get("game_id"))
    buckets = {}
    for move in moves:
        game = index.get(move.get("game_id"))
        if game is None:
            continue
        work = move.get("nodes") or move.get("simulations")
        if not work:
            continue
        key = (game["agent"], game["game"], game["config"], move["version"])
        buckets.setdefault(key, []).append(float(work))
    out = {}
    for key, values in buckets.items():
        values.sort()
        out[key] = values[len(values) // 2]
    return out


def _work_figure(games, moves, meta, out_dir):
    versions = meta.get("versions") or ["v2", "v3"]
    old, new = versions[0], versions[1]
    cells = score_for(games, new, ("agent", "game", "config"))
    work = work_ratios(games, moves)

    fig, ax = plt.subplots(figsize=(7, 5))
    seen = set()
    for (agent, game, config), entry in sorted(cells.items()):
        before = work.get((agent, game, config, old))
        after = work.get((agent, game, config, new))
        if not before or not after:
            continue
        ratio = after / before
        label = agent if agent not in seen else None
        seen.add(agent)
        ax.scatter(ratio, entry["score"], s=48, label=label,
                   color=_COLOURS.get(agent),
                   edgecolor="black", linewidth=0.4, zorder=3)
        if entry["ci_low"] > _NULL or entry["ci_high"] < _NULL:
            # Agent prefix matters: the same game/config appears once per
            # agent, and on Ataxx-easy the two are at opposite ends of the
            # y axis. Colour alone leaves the reader matching against a
            # legend to tell two labelled points apart.
            short = {"alpha_beta": "AB", "mcts": "MC", "heuristic": "HE"}
            ax.annotate("%s %s/%s" % (short.get(agent, agent[:2]),
                                      game[:3], config),
                        (ratio, entry["score"]),
                        textcoords="offset points", xytext=(6, 4),
                        fontsize="x-small")
    ax.axhline(_NULL, linestyle="--", linewidth=1, color="grey")
    ax.axvline(1.0, linestyle="--", linewidth=1, color="grey")
    ax.set_xlabel("work per move, %s / %s  (1.0 = no change)" % (new, old))
    ax.set_ylabel("%s score vs %s  (0.500 = no change)" % (new, old))
    ax.set_ylim(0, 1)
    ax.set_title("More search did not buy strength\n"
                 "labelled points are the cells with a resolved difference",
                 fontsize="medium")
    ax.legend(fontsize="small")
    return _save(fig, out_dir, "fig-duel-work.svg")


def render_all(games, moves, meta, out_dir):
    # type: (list, list, dict, str) -> list
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    written = [_budget_figure(games, meta, out_dir),
               _forest_figure(games, meta, out_dir)]
    if moves:
        written.append(_work_figure(games, moves, meta, out_dir))
    return sorted(written)
