"""SVG figures for the report, rendered from analysis.json.

Kept separate from report.py so the section-rendering tests do not need a
plotting backend, and because matplotlib is slow to import.

DETERMINISM: matplotlib is not reproducible by default. It stamps a <dc:date>
into SVG metadata and salts element ids per process, so two runs over identical
data produce different bytes. Both are pinned below. Without that, the report's
whole "same input, same output" property is false and nobody notices, because
the figures still look right - the same class of defect as D9.
"""
import os

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "search-agents-strategy-games"

import matplotlib.pyplot as plt   # noqa: E402  (must follow use/rcParams)

_SAVE = {"format": "svg", "metadata": {"Date": None}, "bbox_inches": "tight"}
_AGENT_ORDER = ("alpha_beta", "mcts", "heuristic", "random")


def _agents(document):
    known = [a for a in _AGENT_ORDER if a in document["meta"]["agents"]]
    rest = [a for a in document["meta"]["agents"] if a not in _AGENT_ORDER]
    return known + sorted(rest)


def _configs_by_budget(document, game):
    budgets = document["meta"]["budgets"].get(game, {})
    return sorted(budgets, key=lambda c: budgets[c])


def _save(fig, out_dir, name):
    path = os.path.join(out_dir, name)
    fig.savefig(path, **_SAVE)
    plt.close(fig)
    return path


def _score_by_agent(document, out_dir):
    games = document["meta"]["games"]
    agents = _agents(document)
    index = {}
    for row in document["score_table"]:
        index[(row["game"], row["config"], row["agent"])] = row
    fig, axes = plt.subplots(1, len(games), figsize=(5 * len(games), 4),
                             squeeze=False)
    for column, game in enumerate(games):
        ax = axes[0][column]
        configs = _configs_by_budget(document, game)
        width = 0.8 / max(len(configs), 1)
        for offset, config in enumerate(configs):
            xs, ys, lo, hi = [], [], [], []
            for position, agent in enumerate(agents):
                row = index.get((game, config, agent))
                if row is None:
                    continue
                xs.append(position + offset * width)
                ys.append(row["score"])
                lo.append(row["score"] - row["ci_low"])
                hi.append(row["ci_high"] - row["score"])
            ax.bar(xs, ys, width=width, yerr=[lo, hi], capsize=2,
                   label="%.2fs" % document["meta"]["budgets"][game][config])
        ax.set_xticks([p + 0.4 - width / 2 for p in range(len(agents))])
        ax.set_xticklabels(agents, rotation=20, ha="right")
        ax.set_ylim(0, 1.05)
        ax.set_title(game)
        ax.set_ylabel("score rate" if column == 0 else "")
        ax.legend(fontsize="small", title="budget")
    fig.suptitle("Score by agent, with Wilson 95% intervals")
    return _save(fig, out_dir, "fig-score-by-agent.svg")


def _budget_response(document, out_dir):
    games = document["meta"]["games"]
    series = {}
    for row in document["budget_response"]:
        series.setdefault(row["game"], {})[row["agent"]] = row["points"]
    fig, axes = plt.subplots(1, len(games), figsize=(5 * len(games), 4),
                             squeeze=False)
    for column, game in enumerate(games):
        ax = axes[0][column]
        for agent in _agents(document):
            points = series.get(game, {}).get(agent)
            if not points:
                continue
            xs = [p["budget_s"] for p in points]
            ys = [p["score"] for p in points]
            ax.plot(xs, ys, marker="o", label=agent)
            ax.fill_between(xs, [p["ci_low"] for p in points],
                            [p["ci_high"] for p in points], alpha=0.15)
        ax.set_xscale("log")
        ax.set_ylim(0, 1.05)
        ax.set_xlabel("budget (s, log)")
        ax.set_ylabel("score rate" if column == 0 else "")
        ax.set_title(game)
        ax.legend(fontsize="small")
    fig.suptitle("Budget response: does more time buy strength?")
    return _save(fig, out_dir, "fig-budget-response.svg")


def _head_to_head(document, out_dir):
    games = document["meta"]["games"]
    agents = _agents(document)
    pooled = {}
    for row in document["head_to_head"]:
        key = (row["game"], row["agent"], row["opponent"])
        acc = pooled.setdefault(key, [0, 0, 0])
        acc[0] += row["wins"]
        acc[1] += row["draws"]
        acc[2] += row["losses"]
    fig, axes = plt.subplots(1, len(games), figsize=(4.5 * len(games), 4),
                             squeeze=False)
    for column, game in enumerate(games):
        ax = axes[0][column]
        grid = []
        for me in agents:
            line = []
            for opponent in agents:
                acc = pooled.get((game, me, opponent))
                if me == opponent or acc is None:
                    line.append(float("nan"))
                else:
                    total = acc[0] + acc[1] + acc[2]
                    line.append((acc[0] + 0.5 * acc[1]) / total)
            grid.append(line)
        ax.imshow(grid, vmin=0.0, vmax=1.0, cmap="RdYlGn")
        ax.set_xticks(range(len(agents)))
        ax.set_xticklabels(agents, rotation=45, ha="right", fontsize="small")
        ax.set_yticks(range(len(agents)))
        ax.set_yticklabels(agents, fontsize="small")
        for r, line in enumerate(grid):
            for c, value in enumerate(line):
                if value == value:   # not NaN
                    ax.text(c, r, "%.3f" % value, ha="center", va="center",
                            fontsize="small")
        ax.set_title(game)
    fig.suptitle("Head-to-head score (row agent vs column opponent), "
                 "pooled over budgets")
    return _save(fig, out_dir, "fig-head-to-head.svg")


def _sims_per_root(document, out_dir):
    budgets = document["meta"]["budgets"]
    series = {}
    for row in document["simulations_per_root"]:
        budget = budgets.get(row["game"], {}).get(row["config"])
        if budget is None:
            continue
        series.setdefault(row["game"], []).append(
            (budget, row["median_per_root"]))
    fig, ax = plt.subplots(figsize=(6, 4))
    for game in document["meta"]["games"]:
        points = sorted(series.get(game, []))
        if not points:
            continue
        ax.plot([p[0] for p in points], [p[1] for p in points],
                marker="o", label=game)
    ax.axhline(10.0, linestyle="--", linewidth=1, color="grey")
    ax.text(ax.get_xlim()[0], 11.0, "viability floor", fontsize="small",
            color="grey")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("budget (s, log)")
    ax.set_ylabel("median simulations per root move (log)")
    ax.set_title("MCTS search volume against the viability floor")
    ax.legend(fontsize="small")
    return _save(fig, out_dir, "fig-sims-per-root.svg")


def render_all(document, out_dir):
    # type: (dict, str) -> list
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    written = [
        _score_by_agent(document, out_dir),
        _budget_response(document, out_dir),
        _head_to_head(document, out_dir),
        _sims_per_root(document, out_dir),
    ]
    return sorted(written)
