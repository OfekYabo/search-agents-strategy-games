"""Renders the report from analysis.json. Computes nothing.

Two kinds of content live here and they are kept strictly apart:

  - Generated: every table and figure, derived from analysis.json. Same input,
    byte-identical output, so the report can be regenerated for any run.
  - Interpretive: hand-written prose in docs/report/commentary.md, merged in
    by section id.

The generated report is disposable and must never be hand-edited. Prose lives
in the sidecar precisely so that regenerating is unconditionally safe - if
prose lived in the generated file, regeneration would either destroy it or
need round-trip parsing of a file that is supposed to be write-only.
"""
import re
import sys

# Report order. Adding a section here without adding its rendering, or
# renaming one without updating commentary.md, is caught by
# validate_commentary rather than silently dropping prose.
SECTION_IDS = (
    "overview",
    "method",
    "results",
    "budget-response",
    "search-volume",
    "instrument-validation",
    "game-characteristics",
    "limitations",
)

_SECTION_RE = re.compile(r"^<!--\s*section:\s*([a-z0-9-]+)\s*-->\s*$",
                         re.MULTILINE)


def parse_commentary(text):
    # type: (str) -> dict
    """Split the sidecar into {section_id: body}. A body consisting only of
    a TODO marker is treated as empty, so a placeholder reads as a gap rather
    than as prose."""
    sections = {}
    parts = _SECTION_RE.split(text)
    # parts[0] is the preamble before any marker; then (id, body) pairs.
    for index in range(1, len(parts) - 1, 2):
        body = parts[index + 1].strip()
        if body == "<!-- TODO -->":
            body = ""
        sections[parts[index]] = body
    return sections


def validate_commentary(sections, known_ids):
    # type: (dict, tuple) -> None
    unknown = sorted(set(sections) - set(known_ids))
    if unknown:
        raise ValueError(
            "commentary.md has sections matching no report slot: %s. "
            "Rename them or remove them - a renamed report section must not "
            "silently orphan its prose." % ", ".join(unknown))


def commentary_for(sections, section_id):
    # type: (dict, str) -> str
    body = sections.get(section_id, "")
    if not body:
        return "> **[COMMENTARY NEEDED: %s]**" % section_id
    return body


def pool_head_to_head(document):
    # type: (dict) -> dict
    """Pool head-to-head records across configs, keyed (game, agent, opponent).

    Sums wins/draws/losses and recomputes the score. NOT the mean of the three
    config scores: those are different numbers whenever the cells differ in
    size or in variance, and the summed record is the one with a defensible
    confidence interval.
    """
    pooled = {}
    for row in document["head_to_head"]:
        key = (row["game"], row["agent"], row["opponent"])
        acc = pooled.setdefault(key, {"wins": 0, "draws": 0, "losses": 0})
        acc["wins"] += row["wins"]
        acc["draws"] += row["draws"]
        acc["losses"] += row["losses"]
    for entry in pooled.values():
        total = entry["wins"] + entry["draws"] + entry["losses"]
        entry["games"] = total
        entry["score"] = ((entry["wins"] + 0.5 * entry["draws"]) / total
                          if total else 0.0)
    return pooled


def vs_random(document):
    # type: (dict) -> list
    """Every agent's pooled record against the random agent.

    A one-ply evaluator should crush a random opponent. On Isolation the
    heuristic scores only 0.750 against it, against 0.963 on UTTT - and
    Isolation is the designated control game, so a weak control belongs in
    instrument validation where it cannot hide behind an average.
    """
    pooled = pool_head_to_head(document)
    rows = []
    for (game, agent, opponent), entry in sorted(pooled.items()):
        if opponent != "random" or agent == "random":
            continue
        row = {"game": game, "agent": agent}
        row.update(entry)
        rows.append(row)
    return rows


# Presentation order, shared with figures.py so a table and the figure beside
# it never disagree about column order. Anything not listed sorts after.
_AGENT_ORDER = ("alpha_beta", "mcts", "heuristic", "random")


def _agents(document):
    # type: (dict) -> list
    present = document["meta"]["agents"]
    known = [a for a in _AGENT_ORDER if a in present]
    return known + sorted(a for a in present if a not in _AGENT_ORDER)


def _one_row_per_pair(agents):
    # type: (list) -> Any
    """Predicate keeping one direction of each unordered pairing.

    A head-to-head record and its mirror carry the same information: the
    score is the complement and the W-D-L is reversed. In a matrix both
    directions earn their place, because reading a row is how you scan one
    agent against the field. In a flat table they are pure duplication - the
    full per-config listing was 108 rows of which 54 said nothing new.
    """
    rank = dict((a, i) for i, a in enumerate(agents))
    last = len(agents)

    def keep(agent, opponent):
        return rank.get(agent, last) < rank.get(opponent, last)
    return keep


def _table(headers, rows):
    # type: (list, list) -> str
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


def _plain(value):
    # type: (Any) -> str
    """Render a metadata value for a table cell. A nested dict would otherwise
    arrive as a Python repr, braces and quotes and all, in the middle of a
    report someone is meant to read."""
    if isinstance(value, dict):
        return ", ".join("%s=%s" % (k, value[k]) for k in sorted(value))
    if isinstance(value, list):
        return ", ".join(str(v) for v in value)
    return str(value)


def _pct(value):
    return "%.1f%%" % value


def _score(row):
    return "%.3f [%.3f-%.3f]" % (row["score"], row["ci_low"], row["ci_high"])


def render(document, sections, figure_names, run_meta=None):
    # type: (dict, dict, list, dict) -> str
    meta = document["meta"]
    agents = _agents(document)
    games = meta["games"]
    figures_present = set(figure_names)
    pooled = pool_head_to_head(document)
    run_meta = run_meta or {}

    def figure(name, caption):
        if name not in figures_present:
            return ""
        return "\n![%s](figures/%s)\n" % (caption, name)

    def slot(section_id):
        return "\n" + commentary_for(sections, section_id) + "\n"

    parts = []
    parts.append("# Tournament report: %s\n" % (meta["label"] or "unlabelled"))

    # 1. Overview
    errors = sum(r["count"] for r in document["tag_distribution"]
                 if r["tag"] in ("error", "illegal_move", "agent_error"))
    parts.append("## 1. Overview\n")
    parts.append(_table(
        ["property", "value"],
        [["games played", meta["games_total"]],
         ["games", ", ".join(games)],
         ["configs", ", ".join(meta["configs"])],
         ["agents", ", ".join(agents)],
         ["error moves", errors]]))
    parts.append(slot("overview"))

    # 2. Method for this run
    parts.append("## 2. Method for this run\n")
    parts.append(_table(
        ["game", "config", "budget (s)"],
        [[game, config, meta["budgets"][game][config]]
         for game in games
         for config in sorted(meta["budgets"][game],
                              key=lambda c: meta["budgets"][game][c])]))
    if run_meta:
        if run_meta.get("source") == "reconstructed":
            parts.append("\n> These values are **reconstructed**, not "
                         "recorded by the run itself. The tournament does "
                         "not yet write its own metadata.\n")
        parts.append(_table(
            ["property", "value"],
            [[key, _plain(run_meta[key])] for key in sorted(run_meta)
             if key not in ("source", "roster", "starts")]))
    else:
        parts.append("\n> Run metadata was **not recorded by this run**. "
                     "The MCTS rollout parameters, interpreter version and "
                     "host are not present in the CSVs; see "
                     "`experiments/tournament.py` at the run's tag.\n")
    # The roster comes from analysis.json, which is derived from games.csv.
    # run_meta is a claim about the run; this describes what actually ran, and
    # it is the only form that can express one agent label at two versions.
    roster = meta.get("roster") or {}
    if roster:
        parts.append("\n**Agent roster and hyperparameters**, read from "
                     "`games.csv` rather than from metadata, so it describes "
                     "what actually ran\n")
        parts.append(_table(
            ["agent", "version", "hyperparameters"],
            [[key.split("@")[0], key.split("@")[-1],
              _plain(roster[key]) if roster[key] else "-"]
             for key in sorted(roster)]))
    for key in meta.get("roster_conflicts") or []:
        parts.append("\n> **WARNING: %s ran with more than one set of "
                     "hyperparameters in this run.** The run is not what it "
                     "claims to be; do not compare these results until it is "
                     "explained.\n" % key)
    parts.append(slot("method"))

    # 3. Results
    parts.append("## 3. Results\n")
    for game in games:
        parts.append("\n**%s** - head-to-head, pooled over budgets "
                     "(row agent vs column opponent)\n" % game)
        rows = []
        for me in agents:
            line = [me]
            for opponent in agents:
                entry = pooled.get((game, me, opponent))
                line.append("-" if entry is None else "%.3f" % entry["score"])
            rows.append(line)
        parts.append(_table([""] + agents, rows))
    parts.append(figure("fig-head-to-head.svg", "Head-to-head"))
    parts.append(figure("fig-score-by-agent.svg", "Score by agent"))
    keep = _one_row_per_pair(agents)
    parts.append("\n**Non-transitivity check** - each pairing once, pooled "
                 "over budgets. The reverse direction is the complement: "
                 "score `1 - s`, record reversed.\n")
    parts.append(_table(
        ["game", "agent", "opponent", "score", "W-D-L"],
        [[g, a, o, "%.3f" % e["score"],
          "%d-%d-%d" % (e["wins"], e["draws"], e["losses"])]
         for (g, a, o), e in sorted(pooled.items()) if keep(a, o)]))
    parts.append("\n-> Full per-config breakdown: [E1](#e1-full-head-to-head). "
                 "Full score table: [E2](#e2-full-score-table).\n")
    parts.append(slot("results"))

    # 4. Budget response
    parts.append("## 4. Budget response\n")
    for row in document["budget_response"]:
        parts.append("\n**%s / %s**\n" % (row["game"], row["agent"]))
        parts.append(_table(
            ["budget (s)", "config", "score", "games"],
            [[p["budget_s"], p["config"], _score(p), p["games"]]
             for p in row["points"]]))
    parts.append(figure("fig-budget-response.svg", "Budget response"))
    parts.append(slot("budget-response"))

    # 5. Search volume and viability
    parts.append("## 5. Search volume and viability\n")
    parts.append(_table(
        ["game", "config", "agent", "mean sims", "median /root", "p5 /root",
         "% below floor", "verdict"],
        [[r["game"], r["config"], r["agent"], "%.1f" % r["mean_simulations"],
          "%.1f" % r["median_per_root"], "%.1f" % r["p5_per_root"],
          _pct(r["pct_below_floor"]), r["verdict"]]
         for r in document["simulations_per_root"]]))
    parts.append("\n**Alpha-Beta depth reached**\n")
    parts.append(_table(
        ["game", "config", "agent", "median depth", "max depth"],
        # A median is an int for an odd count and a float for an even one, so
        # the raw values mix "4" and "4.0" down one column. Format, don't
        # round: the half-step is real and rounding it away would overstate.
        [[r["game"], r["config"], r["agent"], "%.1f" % r["median_depth"],
          r["max_depth"]] for r in document["search_depth"]]))
    parts.append(figure("fig-sims-per-root.svg", "Simulations per root move"))
    parts.append(slot("search-volume"))

    # 6. Instrument validation
    parts.append("## 6. Instrument validation\n")
    parts.append("\n**Budget compliance** (elapsed / budget)\n")
    parts.append(_table(
        ["game", "config", "agent", "mean", "p99", "max", "moves"],
        [[r["game"], r["config"], r["agent"], _pct(100 * r["mean_ratio"]),
          _pct(100 * r["p99_ratio"]), _pct(100 * r["max_ratio"]), r["moves"]]
         for r in document["budget_compliance"]]))
    parts.append("\n**Every agent against the random agent** - a one-ply "
                 "evaluator should dominate here; a weak control game shows "
                 "up as a low score\n")
    parts.append(_table(
        ["game", "agent", "score", "W-D-L"],
        [[r["game"], r["agent"], "%.3f" % r["score"],
          "%d-%d-%d" % (r["wins"], r["draws"], r["losses"])]
         for r in vs_random(document)]))
    fma = document["first_move_advantage"]
    parts.append("\n**First-move advantage** (decisive games only): "
                 "first %d, second %d, decisive %d, draws excluded %d, "
                 "p = %.4f\n" % (fma["first"], fma["second"], fma["decisive"],
                                 fma["excluded_draws"], fma["p"]))
    parts.append("\n-> Move-tag distribution: "
                 "[E3](#e3-move-tag-distribution).\n")
    parts.append(slot("instrument-validation"))

    # 7. Game characteristics
    parts.append("## 7. Game characteristics\n")
    parts.append(_table(
        ["game", "config", "mean plies", "median plies", "games"],
        [[r["game"], r["config"], "%.1f" % r["mean_plies"],
          r["median_plies"], r["games"]] for r in document["game_length"]]))
    parts.append("\n-> End-reason breakdown: [E4](#e4-end-reasons).\n")
    parts.append(slot("game-characteristics"))

    # 8. Limitations
    parts.append("## 8. Limitations\n")
    parts.append("\nScores are Wilson 95%% intervals. With %d games in the "
                 "smallest head-to-head cell, differences below roughly 0.15 "
                 "are not resolvable. A wall-clock budget makes the run one "
                 "sample rather than a replayable artifact.\n"
                 % min([e["games"] for e in pooled.values()] or [0]))
    parts.append(slot("limitations"))

    # Extras
    parts.append("\n---\n\n## Extras\n")
    parts.append("\n### E1. Full head-to-head\n")
    parts.append("\nOne row per pairing per config. The reverse direction is "
                 "the complement and is not listed.\n")
    parts.append(_table(
        ["game", "config", "agent", "opponent", "score", "W-D-L", "games"],
        [[r["game"], r["config"], r["agent"], r["opponent"], _score(r),
          "%d-%d-%d" % (r["wins"], r["draws"], r["losses"]), r["games"]]
         for r in document["head_to_head"]
         if keep(r["agent"], r["opponent"])]))
    parts.append("\n### E2. Full score table\n")
    parts.append(_table(
        ["game", "config", "agent", "W", "D", "L", "score"],
        [[r["game"], r["config"], r["agent"], r["wins"], r["draws"],
          r["losses"], _score(r)] for r in document["score_table"]]))
    parts.append("\n### E3. Move-tag distribution\n")
    parts.append(_table(
        ["agent", "tag", "count"],
        [[r["agent"], r["tag"], r["count"]]
         for r in document["tag_distribution"]]))
    parts.append("\n### E4. End reasons\n")
    parts.append(_table(
        ["game", "config", "reason", "count"],
        [[r["game"], r["config"], reason, count]
         for r in document["game_length"]
         for reason, count in sorted(r["end_reasons"].items())]))
    parts.append("\n### E5. Provenance\n")
    parts.append("\nRegenerate this report with:\n\n"
                 "```bash\n"
                 "python3 -m experiments.analyse --raw results/raw \\\n"
                 "        --json results/analysis.json --label %s\n"
                 "python3 -m experiments.report --analysis "
                 "results/analysis.json\n"
                 "```\n" % (meta["label"] or "unlabelled"))

    return "\n".join(parts) + "\n"


def load_run_meta(path):
    # type: (str) -> dict
    """Run metadata the CSVs cannot supply - rollout parameters, interpreter,
    host. Absent is a valid state and renders as "not recorded", never as an
    invented value."""
    import json
    import os
    if not os.path.exists(path):
        return {}
    with open(path) as handle:
        return json.load(handle)


def main(argv=None):
    # type: (Any) -> int
    import argparse
    import json
    import os

    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", default="results/analysis.json")
    parser.add_argument("--commentary", default="docs/report/commentary.md")
    parser.add_argument("--out", default="results/report.md")
    parser.add_argument("--figures", default="results/figures")
    # Explicit rather than derived from --analysis. It lives beside the CSVs
    # it describes, in the raw directory, not beside the analysis output.
    parser.add_argument("--run-meta", dest="run_meta",
                        default="results/raw/run_meta.json")
    args = parser.parse_args(argv)

    with open(args.analysis) as handle:
        document = json.load(handle)

    sections = {}
    if os.path.exists(args.commentary):
        with open(args.commentary) as handle:
            sections = parse_commentary(handle.read())
    validate_commentary(sections, SECTION_IDS)

    run_meta = load_run_meta(args.run_meta)

    from experiments import figures
    written = figures.render_all(document, args.figures)
    names = [os.path.basename(p) for p in written]

    text = render(document, sections, names, run_meta=run_meta)
    directory = os.path.dirname(args.out)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(args.out, "w") as handle:
        handle.write(text)

    missing = [i for i in SECTION_IDS if not sections.get(i)]
    if missing:
        sys.stderr.write("warning: %d commentary section(s) unfilled: %s\n"
                         % (len(missing), ", ".join(missing)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
