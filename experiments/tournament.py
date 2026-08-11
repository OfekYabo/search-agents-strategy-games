"""Full round-robin tournament over the grid.

Trials are interleaved across matchups rather than grouped, so that thermal
drift or background load on the host affects every agent equally rather than
accumulating against whichever ran last. This is a correctness requirement of
the methodology, not an optimisation.

Run:  python3 -m experiments.tournament --games all --configs all --trials 20
"""
import argparse
import itertools
import os
import sys
from dataclasses import dataclass
from typing import Any, List, Tuple

from agents import alpha_beta_agent, heuristic_agent, mcts_agent, random_agent
from experiments import runner
from experiments.calibrate import BUDGETS
from experiments.logger import GameLogger

AGENTS = ("random", "heuristic", "alpha_beta", "mcts")

# Historical V1 harness caps. From V2 onward the selected version package owns
# its own caps. They are bounds in each algorithm's native search-structure
# unit, not a claim of equal bytes.
CAPS = {"max_entries": 200000, "max_nodes": 50000}

# MCTS rollout parameters, selected by calibrate.py phase 3 rather than assumed.
# Only the exploration constant has a principled derivation; these three are
# domain-tuned hyperparameters everywhere in the literature.
#
# epsilon=1.0 with sample_k=1 means PURE RANDOM rollouts - no evaluator call
# inside the playout at all. That is a measured result, not an oversight, and it
# inverts the reasoning in PLAN.md that motivated heuristic guidance. Guided
# rollouts cost up to k*D child evaluations each, which starved the tree: at the
# defaults MCTS got 6 simulations per move on UTTT, fewer than its legal moves,
# so it could not try each candidate once. Phase 3 scored this configuration
# best on all three games - 1.00 on Isolation, 1.00 on UTTT, 0.38 on Ataxx -
# against 0.29 for the guided default on UTTT.
#
# These MUST be passed explicitly. mcts_agent.make defaults to the guided
# configuration, so omitting them silently runs the worst config phase 3 found.
MCTS_ROLLOUT = {"epsilon": 1.0, "sample_k": 1, "rollout_depth": 10}


@dataclass(frozen=True)
class Cell:
    game: str
    config: str
    agent_first: str
    agent_second: str
    trial: int


def pairings():
    # type: () -> List[Tuple[str, str]]
    """All 12 directed matchups: every unordered pair in both seat orders."""
    out = []
    for a, b in itertools.combinations(AGENTS, 2):
        out.append((a, b))
        out.append((b, a))
    return out


def build_schedule(games, configs, trials):
    # type: (Tuple[str, ...], Tuple[str, ...], int) -> List[Cell]
    """Interleaved: trial 0 of every matchup, then trial 1, and so on. No two
    consecutive cells share a matchup."""
    schedule = []
    for trial in range(trials):
        for game in games:
            for config in configs:
                for first, second in pairings():
                    schedule.append(Cell(game, config, first, second, trial))
    return schedule


def _game_module(name):
    from games import ataxx, isolation, uttt
    return {"isolation": isolation, "ataxx": ataxx, "uttt": uttt}[name]


def _evaluator(name):
    from evaluation import ataxx_eval, isolation_eval, uttt_eval
    return {"isolation": isolation_eval, "ataxx": ataxx_eval,
            "uttt": uttt_eval}[name]


def _make_agent(name, ev):
    """A fresh agent per game. Alpha-Beta's table and MCTS's tree must never
    carry across games - a table saturated by a finished game would report a
    memory cap on an early move of the next one."""
    if name == "random":
        return random_agent.choose
    if name == "heuristic":
        return heuristic_agent.make(ev.evaluate)
    if name == "alpha_beta":
        return alpha_beta_agent.make(ev.evaluate,
                                     max_entries=CAPS["max_entries"])
    if name == "mcts":
        return mcts_agent.make(ev.evaluate, max_nodes=CAPS["max_nodes"],
                               **MCTS_ROLLOUT)
    raise ValueError("unknown agent %r" % (name,))


class _Evaluator(object):
    """_make_agent takes a module with an `evaluate` attribute; the versioned
    interface passes the function itself. Adapts one to the other."""

    def __init__(self, evaluate):
        self.evaluate = evaluate


class _V1Source(object):
    """Exposes v1's inline agent construction under the same interface the
    versioned packages provide, so the tournament has one code path.

    v1 has no package of its own and must not grow one: it is frozen, and its
    hyperparameters living here in the harness is exactly the mistake the
    versioned packages exist to correct. This shim reads them rather than
    moving them.
    """

    VERSION = "v1"
    AGENTS = AGENTS
    CAPS = CAPS
    SEPARATE_RNG_STREAMS = False

    @staticmethod
    def build(label, evaluate):
        return _make_agent(label, _Evaluator(evaluate))

    @staticmethod
    def params(label):
        if label == "alpha_beta":
            return {"max_entries": CAPS["max_entries"]}
        if label == "mcts":
            out = {"max_nodes": CAPS["max_nodes"]}
            out.update(MCTS_ROLLOUT)
            return out
        return {}


def agent_source(version):
    # type: (str) -> Any
    """The package supplying agents for `version`, or the v1 shim."""
    if version == "v1":
        return _V1Source
    if version == "v2":
        from agents import v2
        return v2
    if version == "v3":
        from agents import v3
        return v3
    raise ValueError("unknown agent version %r" % (version,))


def evaluator_source(version, game):
    # type: (str, str) -> Any
    """Evaluators are versioned alongside agents and always move together, so
    one version string describes both."""
    if version == "v1":
        return _evaluator(game)
    package = __import__("evaluation.%s" % version, fromlist=["x"])
    return getattr(package, "%s_eval" % game)


def host_info():
    # type: () -> dict
    """The machine, in the detail a wall-clock budget makes necessary.

    `platform.platform()` gives the kernel and glibc and says nothing about
    cores, memory or the CPU - which are exactly the things that decide how
    much search a budget buys. Recording only that string is how the V1
    metadata ended up less informative than the note someone wrote by hand.

    Every source here is stdlib except the virtualisation probe, which
    degrades to "unknown" rather than failing: this runs inside the
    measurement path and must never be the reason a tournament does not start.
    """
    import platform
    import shutil
    import subprocess

    def _first_line(path, prefix=""):
        try:
            with open(path) as handle:
                for line in handle:
                    if line.startswith(prefix):
                        return line.split("=", 1)[-1].split(":", 1)[-1] \
                            .strip().strip('"')
        except (IOError, OSError):
            pass
        return "unknown"

    try:
        ram = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        ram = 0
    try:
        disk = shutil.disk_usage("/").total
    except OSError:
        disk = 0
    try:
        virt = subprocess.check_output(["systemd-detect-virt"],
                                       stderr=subprocess.STDOUT).decode().strip()
    except Exception:
        virt = "unknown"

    return {
        "cpu_count": os.cpu_count() or 0,
        "cpu_model": _first_line("/proc/cpuinfo", "model name"),
        "ram_gb": round(ram / (1024.0 ** 3), 2),
        "disk_gb": round(disk / (1024.0 ** 3), 2),
        "os": _first_line("/etc/os-release", "PRETTY_NAME"),
        "kernel": platform.platform(),
        "arch": platform.machine(),
        "virtualisation": virt,
    }


def _load_meta(path):
    # type: (str) -> dict
    import json
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as handle:
            return json.load(handle)
    except ValueError:
        return {}


def _save_meta(path, meta):
    # type: (str, dict) -> None
    import json
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w") as handle:
        json.dump(meta, handle, sort_keys=True, indent=2)
        handle.write("\n")


def record_run_finished(path, wall_clock_seconds, played=None):
    # type: (str, float, Any) -> None
    """Stamp the run's wall clock into run_meta.

    Search time is derivable from moves.csv and matches wall clock to within
    0.1% on a healthy run. Recording both lets the report compare them, and
    the gap between them is exactly the time the run was not searching - a
    stall, a pause, or something else competing for the host.

    Two rules, both learned the hard way on the V2 run. The unit is startable
    on boot, so a completed run gets re-entered: the tournament found all 2700
    games present, played none, finished in 0.206 s and stamped that as the
    wall clock, destroying the recorded 9.81 h. So a resume that played
    **nothing** must not touch the figure at all.

    And a resume that *did* play adds to the total rather than replacing it,
    because the run's real cost is the sum of the attempts that did work, not
    whichever attempt happened to finish last.
    """
    if played == 0:
        return
    meta = _load_meta(path)
    if not meta:
        return
    previous = meta.get("wall_clock_seconds") or 0.0
    meta["wall_clock_seconds"] = round(previous + wall_clock_seconds, 3)
    _save_meta(path, meta)


def write_run_meta(path, version, games, configs, trials, schedule_size):
    # type: (str, str, tuple, tuple, int, int) -> None
    """Record what this run is, at startup.

    The v1 run could not say from its own data which rollout parameters
    produced it - they lived only as a constant in this file. That gap caused
    defect D4 and forced the rewrite of finding F3.

    A restart appends to `starts` rather than clobbering, so a resumed run
    keeps the history of every attempt instead of only the last one.
    """
    import json
    import platform
    import subprocess

    source = agent_source(version)
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            stderr=subprocess.STDOUT).decode().strip()
    except Exception:
        commit = "unknown"

    start = {"python": sys.version.split()[0],
             "platform": platform.platform(),
             "commit": commit}

    existing = _load_meta(path)

    meta = {
        "source": "recorded",
        "experiment": "main_tournament",
        "agent_version": version,
        "games": list(games),
        "configs": list(configs),
        "trials": trials,
        "schedule_size": schedule_size,
        "budgets": dict((g, dict(BUDGETS[g])) for g in games),
        "roster": dict((label, source.params(label))
                       for label in source.AGENTS),
        "rng_streams": ("per_side" if getattr(source,
                                               "SEPARATE_RNG_STREAMS", False)
                        else "shared"),
        "python": start["python"],
        "platform": start["platform"],
        "host": host_info(),
        "commit": commit,
        "starts": existing.get("starts", []) + [start],
    }

    # Merge, never replace. Fields added after a run - a measured wall clock,
    # a provenance note on the host block - are not reproducible from the
    # environment, so rebuilding the file from scratch on a restart silently
    # deletes them. Anything this function does not own is carried forward.
    merged = dict(existing)
    for key, value in meta.items():
        if key == "host" and isinstance(existing.get("host"), dict):
            host = dict(existing["host"])
            host.update(value)
            merged["host"] = host
        else:
            merged[key] = value
    _save_meta(path, merged)


def run(schedule, out_dir, workers=1, resume=True, version="v1"):
    # type: (List[Cell], str, int, bool) -> int
    if workers != 1:
        raise ValueError(
            "Parallel tournament execution is disabled for experimental "
            "validity; use --workers 1.")

    games_path = os.path.join(out_dir, "games.csv")
    moves_path = os.path.join(out_dir, "moves.csv")
    logger = GameLogger(games_path, moves_path)
    done = logger.completed_ids() if resume else set()

    source = agent_source(version)
    caps = getattr(source, "CAPS", CAPS)
    played = 0
    for index, cell in enumerate(schedule):
        game = _game_module(cell.game)
        ev = evaluator_source(version, cell.game)
        budget = BUDGETS[cell.game][cell.config]
        config = {"name": cell.config, "time_budget_s": budget,
                  "max_nodes": caps["max_nodes"],
                  "max_entries": caps["max_entries"]}
        seed = runner.game_seed(cell.game, cell.agent_first, cell.agent_second,
                                cell.config, cell.trial)
        # Same function the runner uses - never re-derive the format here, or
        # --resume silently stops matching and re-runs completed games.
        record_id = runner.game_id(cell.game, cell.agent_first,
                                   cell.agent_second, cell.config, cell.trial)
        if record_id in done:
            continue
        agents = (source.build(cell.agent_first, ev.evaluate),
                  source.build(cell.agent_second, ev.evaluate))
        record = runner.play_game(
            game, agents, (cell.agent_first, cell.agent_second), config, seed,
            ply_cap=300, trial=cell.trial, workers=workers,
            agent_versions=(version, version),
            agent_params=(source.params(cell.agent_first),
                          source.params(cell.agent_second)),
            separate_rng_streams=getattr(source, "SEPARATE_RNG_STREAMS",
                                         False))
        logger.write(record)
        played += 1
        if played % 20 == 0:
            print("  %d/%d games" % (index + 1, len(schedule)))
            sys.stdout.flush()
    logger.close()
    return played


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--games", default="all")
    parser.add_argument("--configs", default="all")
    parser.add_argument("--trials", type=int, default=20)
    parser.add_argument("--out", default="results/raw")
    parser.add_argument(
        "--workers", type=int, default=1,
        help="must remain 1; parallel execution is disabled for fair "
             "wall-clock-budget experiments")
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--agent-version", dest="agent_version",
                        default="v1")
    args = parser.parse_args(argv)

    games = (("isolation", "uttt", "ataxx") if args.games == "all"
             else tuple(args.games.split(",")))
    configs = (("easy", "main", "hard") if args.configs == "all"
               else tuple(args.configs.split(",")))
    schedule = build_schedule(games, configs, args.trials)
    print("scheduled %d games across %d matchups" % (len(schedule), 12))
    write_run_meta(os.path.join(args.out, "run_meta.json"),
                   args.agent_version, games, configs, args.trials,
                   len(schedule))
    import time
    started = time.time()
    played = run(schedule, args.out, workers=args.workers,
                 resume=not args.no_resume, version=args.agent_version)
    record_run_finished(os.path.join(args.out, "run_meta.json"),
                        time.time() - started, played=played)
    print("played %d games (rest already present)" % played)
    return 0


if __name__ == "__main__":
    sys.exit(main())
