"""Report for the version duel.

Deliberately not the full tournament report. With the same agent type on both
sides there is no field, so score tables, budget response, first-move advantage
and game characteristics are all meaningless here. One question is being asked -
**is the newer version stronger?** - and the report is shaped around it.

The precision lives in the pooled rows, not the per-cell ones. A single cell
holds 80 games at 40 trials and resolves about +/-0.11, which will not settle
the effect sizes this project produces. Pooling nine cells per agent gives 720
games and about +/-0.037, which will.

Run:
    python3 -m experiments.duel_report --raw results/duel \\
        --out results/duel/report.md
"""
import argparse
import csv
import json
import os
import sys

from experiments.analyse import wilson_interval
from experiments.report import commentary_for, parse_commentary, \
    validate_commentary

SECTION_IDS = ("duel-overview", "duel-method", "duel-results",
               "duel-search-volume", "duel-limitations")


def load(raw_dir):
    # type: (str) -> tuple
    with open(os.path.join(raw_dir, "games.csv"), newline="") as handle:
        games = list(csv.DictReader(handle))
    moves = []
    moves_path = os.path.join(raw_dir, "moves.csv")
    if os.path.exists(moves_path):
        with open(moves_path, newline="") as handle:
            moves = list(csv.DictReader(handle))
    meta = {}
    meta_path = os.path.join(raw_dir, "run_meta.json")
    if os.path.exists(meta_path):
        with open(meta_path) as handle:
            meta = json.load(handle)
    return games, moves, meta


def score_for(rows, target, keys=()):
    # type: (list, str, tuple) -> dict
    """Record for `target` version, grouped by `keys`, pooled over seat order.

    Pooling the two seat orders is what makes a cell a matched pair: if the
    newer version only wins from one seat, that is first-move advantage rather
    than a version effect.
    """
    out = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        entry = out.setdefault(key, {"wins": 0, "draws": 0, "losses": 0})
        target_is_first = row["first_version"] == target
        if row["winner"] == "draw":
            entry["draws"] += 1
        elif (row["winner"] == "first") == target_is_first:
            entry["wins"] += 1
        else:
            entry["losses"] += 1
    for entry in out.values():
        entry.update(wilson_interval(entry["wins"], entry["draws"],
                                     entry["losses"]))
    return out


def _verdict(entry):
    if entry["ci_low"] > 0.5:
        return "**stronger**"
    if entry["ci_high"] < 0.5:
        return "**WEAKER**"
    return "not resolved"


def _row(entry):
    return ("%.3f | [%.3f, %.3f] | %d-%d-%d | %d | %s"
            % (entry["score"], entry["ci_low"], entry["ci_high"],
               entry["wins"], entry["draws"], entry["losses"],
               entry["games"], _verdict(entry)))


def render(games, moves, meta, sections=None, figure_names=()):
    # type: (list, list, dict, dict, tuple) -> str
    sections = sections or {}
    figures_present = set(figure_names)

    def figure(name, caption):
        if name not in figures_present:
            return ""
        return "\n![%s](figures/%s)\n" % (caption, name)
    versions = meta.get("versions") or ["v2", "v3"]
    old, new = versions[0], versions[1]
    if not games:
        return "# Version duel: %s vs %s\n\nNo games found.\n" % (old, new)

    def slot(section_id):
        return "\n" + commentary_for(sections, section_id) + "\n"

    parts = []
    parts.append("# Version duel: %s vs %s\n" % (old, new))
    parts.append("Every game is one agent type against **itself at two "
                 "versions**, on the same game, at the same time budget, with "
                 "the same memory bound. Only the version differs. Both seat "
                 "orders are played from one base seed, so each trial is a "
                 "matched pair rather than two independent samples.\n")
    parts.append("\n**All scores below are from %s's point of view.** 0.500 "
                 "means the versions are indistinguishable; an interval that "
                 "excludes 0.500 means the difference is resolved.\n" % new)
    parts.append(slot("duel-overview"))

    parts.append("\n## Method\n")
    parts.append(_table(
        ["property", "value"],
        [["versions", "%s (first listed) vs %s" % (old, new)],
         ["games", len({r["game"] for r in games})],
         ["configs", len({r["config"] for r in games})],
         ["agents", ", ".join(sorted({r["agent"] for r in games}))],
         ["total games", len(games)],
         ["RNG", meta.get("rng_streams", "per_side")]]))
    if meta.get("rng_note"):
        parts.append("\n> **On randomness.** %s\n" % meta["rng_note"])
    parts.append(slot("duel-method"))

    parts.append("\n## Results\n")
    overall = score_for(games, new, ())[()]
    parts.append("\n**Overall, pooled across every cell** - the widest and "
                 "therefore most precise view:\n")
    parts.append(_table(
        ["score (%s)" % new, "95% CI", "W-D-L", "games", "verdict"],
        [_row(overall).split(" | ")]))

    parts.append("\n**By agent** - the primary unit, because a version "
                 "change need not affect every agent the same way\n")
    by_agent = score_for(games, new, ("agent",))
    parts.append(_table(
        ["agent", "score (%s)" % new, "95% CI", "W-D-L", "games", "verdict"],
        [[k[0]] + _row(e).split(" | ") for k, e in sorted(by_agent.items())]))

    parts.append("\n**By agent and game**\n")
    by_ag = score_for(games, new, ("agent", "game"))
    parts.append(_table(
        ["agent", "game", "score (%s)" % new, "95% CI", "W-D-L", "games",
         "verdict"],
        [[k[0], k[1]] + _row(e).split(" | ")
         for k, e in sorted(by_ag.items())]))
    parts.append(figure("fig-duel-budget.svg",
                        "Score against budget, per agent and game"))
    parts.append(slot("duel-results"))

    parts.append("\n## Every cell\n")
    parts.append("\nOne row per agent, game and budget. These are for texture: "
                 "a single cell is too small to resolve anything on its own, "
                 "which is why the pooled rows above carry the result.\n")
    cells = score_for(games, new, ("agent", "game", "config"))
    parts.append(_table(
        ["agent", "game", "config", "score (%s)" % new, "95% CI", "W-D-L",
         "games", "verdict"],
        [[k[0], k[1], k[2]] + _row(e).split(" | ")
         for k, e in sorted(cells.items())]))
    parts.append(figure("fig-duel-forest.svg",
                        "Every cell against the 0.500 null"))

    parts.append("\n## Search volume\n")
    parts.append("\nWhat each version actually did with the same budget. This "
                 "is where a difference in *strength* would have to come "
                 "from, and its absence beside a large difference here is "
                 "itself a result.\n")
    volume = _search_volume(games, moves)
    if volume:
        parts.append(_table(
            ["agent", "game", "config", "version", "median work/move",
             "median sims/root"],
            volume))
    parts.append(figure("fig-duel-work.svg",
                        "Work gained against strength gained"))
    parts.append(slot("duel-search-volume"))

    parts.append("\n## Limitations\n")
    parts.append(slot("duel-limitations"))
    return "\n".join(parts) + "\n"


def _search_volume(games, moves):
    # type: (list, list) -> list
    # .get(): a caller should never lose the whole report to one
    # malformed row, and the volume table is supporting evidence.
    index = dict((r["game_id"], r) for r in games if r.get("game_id"))
    buckets = {}
    for m in moves:
        game = index.get(m.get("game_id"))
        if game is None:
            continue
        work = m["nodes"] or m["simulations"]
        if not work:
            continue
        key = (game["agent"], game["game"], game["config"], m["version"])
        entry = buckets.setdefault(key, {"work": [], "per_root": []})
        entry["work"].append(float(work))
        legal = float(m["legal_move_count"] or 0)
        if m["simulations"] and legal > 0:
            entry["per_root"].append(float(m["simulations"]) / legal)
    rows = []
    for key, entry in sorted(buckets.items()):
        work = sorted(entry["work"])
        per_root = sorted(entry["per_root"])
        rows.append([key[0], key[1], key[2], key[3],
                     "%.0f" % work[len(work) // 2],
                     "%.1f" % per_root[len(per_root) // 2] if per_root else "-"])
    return rows


def _table(headers, rows):
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--commentary", default="")
    parser.add_argument("--figures", default="")
    args = parser.parse_args(argv)

    sections = {}
    if args.commentary and os.path.exists(args.commentary):
        with open(args.commentary) as handle:
            sections = parse_commentary(handle.read())
    validate_commentary(sections, SECTION_IDS)

    games, moves, meta = load(args.raw)
    names = ()
    if args.figures:
        from experiments import duel_figures
        names = tuple(os.path.basename(p) for p in
                      duel_figures.render_all(games, moves, meta,
                                              args.figures))
    text = render(games, moves, meta, sections=sections, figure_names=names)
    missing = [i for i in SECTION_IDS if not sections.get(i)]
    if missing:
        sys.stderr.write("warning: %d commentary section(s) unfilled: %s\n"
                         % (len(missing), ", ".join(missing)))
    if args.out:
        directory = os.path.dirname(args.out)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(args.out, "w") as handle:
            handle.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
