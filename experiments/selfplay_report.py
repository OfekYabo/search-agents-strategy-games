"""Report for the asymmetric-time self-play experiment.

`experiments.analyse` cannot read this data: the self-play CSVs use their own
schema (`first_budget_s`/`second_budget_s` instead of an agent pairing), so
without this the experiment produces numbers nobody reads.

The question it answers is narrow and worth stating exactly: holding the
algorithm, evaluator, game and memory bound fixed, **how much playing strength
does extra per-move time buy?** Every game is one agent against an identical
copy of itself, differing only in budget.

Run:
    python3 -m experiments.selfplay_report \\
        --raw results/v3/time-selfplay-mcts --out results/v3/selfplay-mcts.md
"""
import argparse
import csv
import os
import sys

from experiments.analyse import wilson_interval
from experiments.report import commentary_for, parse_commentary, \
    validate_commentary

# Same sidecar mechanism as the main report: generated content is disposable
# and regenerated from scratch, hand-written interpretation lives in its own
# file and is merged in by id. Without this the only prose here would be
# generated, and there would be nowhere to put a reading of the numbers that
# survives the next run.
SECTION_IDS = ("selfplay-overview", "selfplay-results")


def load(raw_dir):
    # type: (str) -> list
    with open(os.path.join(raw_dir, "games.csv"), newline="") as handle:
        return list(csv.DictReader(handle))


def budget_pairs(rows):
    # type: (list) -> dict
    """Per (game, low, high): the higher-budget side's record.

    Both seat orders are pooled, which is the point of running them: if the
    larger budget only wins from one seat, that is first-move advantage rather
    than the effect of time.
    """
    out = {}
    for row in rows:
        first = float(row["first_budget_s"])
        second = float(row["second_budget_s"])
        low, high = min(first, second), max(first, second)
        if low == high:
            continue
        key = (row["game"], low, high)
        entry = out.setdefault(key, {"wins": 0, "draws": 0, "losses": 0,
                                     "plies": 0, "games": 0})
        entry["games"] += 1
        entry["plies"] += int(row["plies"])
        winner = row["winner"]
        # Which seat held the larger budget this game?
        high_is_first = first >= second
        if winner == "draw":
            entry["draws"] += 1
        elif (winner == "first") == high_is_first:
            entry["wins"] += 1
        else:
            entry["losses"] += 1
    for entry in out.values():
        entry.update(wilson_interval(entry["wins"], entry["draws"],
                                     entry["losses"]))
    return out


def render(rows, label, sections=None):
    # type: (list, str, dict) -> str
    sections = sections or {}
    if not rows:
        return "# Self-play time scaling: %s\n\nNo games found.\n" % label

    table = budget_pairs(rows)
    agents = sorted({r["agent"] for r in rows})
    parts = []
    parts.append("# Self-play time scaling: %s\n" % label)
    parts.append("Agent: **%s**. Every game is this agent against an identical "
                 "copy of itself; the *only* difference between the two seats "
                 "is the per-move time budget. Both seat orders are played "
                 "with the same base seed and independent per-seat RNG "
                 "streams, so a result cannot come from seat advantage or from "
                 "one side consuming the other's random numbers.\n"
                 % ", ".join(agents))
    parts.append("\n" + commentary_for(sections, "selfplay-overview") + "\n")
    parts.append("\n**Score is from the point of view of the side with the "
                 "LARGER budget.** 0.500 means extra time bought nothing; an "
                 "interval that excludes 0.500 means it bought something "
                 "measurable.\n")
    parts.append("\n| game | budget | vs | score (higher budget) | 95% CI | "
                 "W-D-L | games | mean plies |")
    parts.append("|---|---|---|---|---|---|---|---|")
    decisive = 0
    for (game, low, high), e in sorted(table.items()):
        marker = ""
        if e["ci_low"] > 0.5:
            marker = "  **more time wins**"
            decisive += 1
        elif e["ci_high"] < 0.5:
            marker = "  **more time LOSES**"
            decisive += 1
        parts.append("| %s | %.2fs | %.2fs | %.3f%s | [%.3f, %.3f] | %d-%d-%d "
                     "| %d | %.1f |"
                     % (game, high, low, e["score"], marker, e["ci_low"],
                        e["ci_high"], e["wins"], e["draws"], e["losses"],
                        e["games"], e["plies"] / float(e["games"])))

    parts.append("\n## Reading this\n")
    parts.append("%d of %d budget pairs have an interval that excludes 0.500. "
                 "A pair that includes it is not evidence that time does "
                 "nothing - with these sample sizes it is usually just too "
                 "few games to tell.\n" % (decisive, len(table)))
    parts.append("\nThis experiment deliberately does **not** answer whether "
                 "one algorithm beats another; every game here is an agent "
                 "against itself. It isolates the budget axis alone, which the "
                 "main tournament cannot do because there both the agent and "
                 "the budget change together.\n")

    parts.append("\n" + commentary_for(sections, "selfplay-results") + "\n")
    return "\n".join(parts) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", required=True)
    parser.add_argument("--out", default="")
    parser.add_argument("--label", default="")
    parser.add_argument("--commentary", default="")
    args = parser.parse_args(argv)

    sections = {}
    if args.commentary and os.path.exists(args.commentary):
        with open(args.commentary) as handle:
            sections = parse_commentary(handle.read())
    validate_commentary(sections, SECTION_IDS)

    rows = load(args.raw)
    text = render(rows, args.label or os.path.basename(args.raw.rstrip("/")),
                  sections=sections)
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
