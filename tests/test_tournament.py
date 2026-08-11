import os
import shutil
import tempfile
import unittest

from experiments import tournament


class PairingTest(unittest.TestCase):
    def test_twelve_directed_matchups_from_four_agents(self):
        p = tournament.pairings()
        self.assertEqual(len(p), 12)
        self.assertEqual(len(set(p)), 12)

    def test_each_pairing_appears_in_both_seat_orders(self):
        p = set(tournament.pairings())
        for a, b in p:
            self.assertIn((b, a), p, "%s vs %s missing its reverse" % (a, b))

    def test_no_agent_plays_itself(self):
        for a, b in tournament.pairings():
            self.assertNotEqual(a, b)


class ScheduleTest(unittest.TestCase):
    def setUp(self):
        self.schedule = tournament.build_schedule(
            games=("isolation",), configs=("main",), trials=3)

    def test_covers_every_matchup_and_trial(self):
        self.assertEqual(len(self.schedule), 12 * 3)

    def test_trials_are_interleaved_not_grouped_by_matchup(self):
        # Consecutive cells must not repeat the same matchup, so that timing
        # drift is spread across agents rather than accumulating against one.
        matchups = [(c.agent_first, c.agent_second) for c in self.schedule]
        repeats = sum(1 for i in range(1, len(matchups))
                      if matchups[i] == matchups[i - 1])
        self.assertEqual(repeats, 0, "schedule is grouped, not interleaved")

    def test_all_trials_of_a_matchup_are_present_exactly_once(self):
        seen = {}
        for c in self.schedule:
            key = (c.agent_first, c.agent_second, c.trial)
            self.assertNotIn(key, seen)
            seen[key] = True
        self.assertEqual(len(seen), 36)


class RunTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_runs_a_tiny_grid_and_writes_both_csvs(self):
        schedule = [c for c in tournament.build_schedule(
            games=("isolation",), configs=("hard",), trials=1)
            if "alpha_beta" not in (c.agent_first, c.agent_second)
            and "mcts" not in (c.agent_first, c.agent_second)]
        tournament.run(schedule, self.dir, resume=False)
        self.assertTrue(os.path.exists(os.path.join(self.dir, "games.csv")))
        self.assertTrue(os.path.exists(os.path.join(self.dir, "moves.csv")))

    def test_resume_skips_already_completed_games(self):
        schedule = [c for c in tournament.build_schedule(
            games=("isolation",), configs=("hard",), trials=1)
            if c.agent_first == "random" and c.agent_second == "heuristic"]
        tournament.run(schedule, self.dir, resume=False)
        import csv
        with open(os.path.join(self.dir, "games.csv")) as h:
            first = len(list(csv.DictReader(h)))
        tournament.run(schedule, self.dir, resume=True)
        with open(os.path.join(self.dir, "games.csv")) as h:
            second = len(list(csv.DictReader(h)))
        self.assertEqual(first, second, "resume re-ran completed games")



class CalibratedParameterTest(unittest.TestCase):
    """The tournament must use the parameters calibration selected.

    mcts_agent.make defaults to the guided rollout configuration, which phase 3
    ranked worst on every game. Omitting the explicit parameters would silently
    run a handicapped MCTS and the study would measure the wrong thing.
    """

    def test_mcts_rollout_parameters_are_the_calibrated_ones(self):
        self.assertEqual(tournament.MCTS_ROLLOUT,
                         {"epsilon": 1.0, "sample_k": 1, "rollout_depth": 10})

    def test_the_mcts_agent_is_built_with_them_not_with_make_defaults(self):
        import agents.mcts_agent as m
        seen = {}
        original = m.make

        def spy(evaluate, **kwargs):
            seen.update(kwargs)
            return original(evaluate, **kwargs)

        m.make = spy
        try:
            from evaluation import isolation_eval
            tournament._make_agent("mcts", isolation_eval)
        finally:
            m.make = original
        for key, value in tournament.MCTS_ROLLOUT.items():
            self.assertEqual(seen.get(key), value,
                             "%s was not passed through to mcts_agent.make" % key)
        self.assertEqual(seen.get("max_nodes"), tournament.CAPS["max_nodes"])


class VersionSelectionTest(unittest.TestCase):
    def test_default_is_v1_so_old_commands_reproduce_v1(self):
        source = tournament.agent_source("v1")
        self.assertEqual(source.VERSION, "v1")
        self.assertEqual(source.AGENTS, tournament.AGENTS)

    def test_v1_shim_builds_the_same_agents_as_the_inline_path(self):
        from evaluation import isolation_eval
        source = tournament.agent_source("v1")
        for label in tournament.AGENTS:
            self.assertTrue(
                callable(source.build(label, isolation_eval.evaluate)))

    def test_v2_and_v3_are_selectable_and_report_their_own_versions(self):
        self.assertEqual(tournament.agent_source("v2").VERSION, "v2")
        self.assertEqual(tournament.agent_source("v3").VERSION, "v3")

    def test_unknown_version_raises(self):
        with self.assertRaises(ValueError):
            tournament.agent_source("v9")

    def test_v1_shim_exposes_the_harness_constants_as_its_params(self):
        source = tournament.agent_source("v1")
        self.assertEqual(source.params("mcts")["epsilon"], 1.0)
        self.assertEqual(source.params("random"), {})

    def test_evaluators_follow_the_agent_version(self):
        self.assertEqual(
            tournament.evaluator_source("v2", "isolation").__name__,
            "evaluation.v2.isolation_eval")


class RunMetaTest(unittest.TestCase):
    def _write(self, path, version="v2"):
        tournament.write_run_meta(path, version, ("ataxx",), ("hard",), 25, 300)

    def test_writes_the_roster_with_versions_and_params(self):
        import json
        import os
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "run_meta.json")
        self._write(path)
        with open(path) as handle:
            meta = json.load(handle)
        self.assertEqual(meta["agent_version"], "v2")
        self.assertEqual(meta["trials"], 25)
        self.assertEqual(meta["schedule_size"], 300)
        self.assertEqual(meta["source"], "recorded")
        self.assertIn("python", meta)
        self.assertIn("platform", meta)
        self.assertEqual(meta["roster"]["mcts"]["epsilon"], 1.0)

    def test_a_restart_appends_rather_than_clobbering(self):
        import json
        import os
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "run_meta.json")
        self._write(path)
        self._write(path)
        with open(path) as handle:
            meta = json.load(handle)
        self.assertEqual(len(meta["starts"]), 2)

class HostInfoTest(unittest.TestCase):
    """A wall-clock budget is only meaningful relative to the machine that
    produced it, so the host belongs in the data. platform.platform() alone
    gives the kernel and glibc and says nothing about cores, memory or the
    CPU - which are the parts that decide how much search a budget buys."""

    def test_records_the_specs_that_decide_how_much_search_a_budget_buys(self):
        host = tournament.host_info()
        for key in ("cpu_count", "ram_gb", "disk_gb", "os", "kernel",
                    "cpu_model", "virtualisation"):
            self.assertIn(key, host)
        self.assertGreater(host["cpu_count"], 0)
        self.assertGreater(host["ram_gb"], 0)

    def test_host_reaches_run_meta(self):
        import json
        import os
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "run_meta.json")
        tournament.write_run_meta(path, "v2", ("ataxx",), ("hard",), 25, 300)
        with open(path) as handle:
            meta = json.load(handle)
        self.assertIn("host", meta)
        self.assertEqual(meta["host"]["cpu_count"], tournament.host_info()["cpu_count"])

class RunMetaDurabilityTest(unittest.TestCase):
    """A completed run's metadata must survive being re-entered.

    The unit is enabled, so a reboot restarts it. On the V2 run that happened:
    the tournament found all 2700 games present, played none, finished in
    0.206 s, and stamped that as the run's wall clock - destroying the
    recorded 9.81 h. It also rebuilt run_meta from scratch, discarding fields
    added after the run.
    """

    def _meta(self, path):
        import json
        with open(path) as handle:
            return json.load(handle)

    def _fresh(self):
        import os
        import tempfile
        path = os.path.join(tempfile.mkdtemp(), "run_meta.json")
        tournament.write_run_meta(path, "v2", ("ataxx",), ("hard",), 25, 300)
        return path

    def test_a_no_op_resume_does_not_overwrite_the_wall_clock(self):
        path = self._fresh()
        tournament.record_run_finished(path, 35325.0, played=300)
        tournament.record_run_finished(path, 0.206, played=0)
        self.assertAlmostEqual(self._meta(path)["wall_clock_seconds"], 35325.0)

    def test_a_resume_that_played_games_accumulates_rather_than_replaces(self):
        """Two attempts that each did work took the sum of their wall clocks,
        not whichever finished last."""
        path = self._fresh()
        tournament.record_run_finished(path, 100.0, played=10)
        tournament.record_run_finished(path, 50.0, played=5)
        self.assertAlmostEqual(self._meta(path)["wall_clock_seconds"], 150.0)

    def test_restarting_preserves_fields_added_after_the_run(self):
        import json
        path = self._fresh()
        meta = self._meta(path)
        meta["wall_clock_source"] = "measured by hand"
        meta["host"]["source"] = "measured after the fact"
        with open(path, "w") as handle:
            json.dump(meta, handle, sort_keys=True, indent=2)
        tournament.write_run_meta(path, "v2", ("ataxx",), ("hard",), 25, 300)
        after = self._meta(path)
        self.assertEqual(after["wall_clock_source"], "measured by hand")
        self.assertEqual(after["host"]["source"], "measured after the fact")
        self.assertEqual(len(after["starts"]), 2)


if __name__ == "__main__":
    unittest.main()
