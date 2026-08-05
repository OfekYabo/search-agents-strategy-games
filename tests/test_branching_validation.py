import unittest

from experiments.measure_branching import measure
from games import ataxx, isolation, uttt


class MeasurementShapeTest(unittest.TestCase):
    def test_isolation_matches_its_derived_bounds(self):
        stats = measure(isolation, n_games=300, seed=1)
        self.assertEqual(stats.mean_by_ply[0], 11.0,
                         "ply-1 branching is 11 - the southward ray stops "
                         "before the opposing pawn")
        self.assertLessEqual(stats.max_b, 16, "16 is the theoretical maximum")
        self.assertLessEqual(stats.mean_length, 23.0)

    def test_uttt_first_ply_offers_all_81_cells(self):
        stats = measure(uttt, n_games=200, seed=2)
        self.assertEqual(stats.mean_by_ply[0], 81.0)
        self.assertLessEqual(stats.mean_length, 81.0)


class AtaxxCurveGateTest(unittest.TestCase):
    """The gate.

    Thresholds here are set from a measurement already taken on this
    implementation, not guessed, and the tightest of them is derived by hand.

    Reference for comparison: Ribeiro and Figueiredo (ENIAC 2018) report about 20
    at ply 1 and a peak near 92 around ply 25, over roughly 100-ply games. Our
    absolute figures differ for two understood reasons and that is expected:
    their measurement is not of uniformly random play, and our board has 49
    playable cells against their 47 because we use no blocked squares. What
    should agree is the SHAPE - a rise to several times the opening branching
    factor, then a decline - and the relative position of the peak.
    """

    @classmethod
    def setUpClass(cls):
        cls.stats = measure(ataxx, n_games=120, seed=3)

    def test_ply_one_branching_is_exactly_sixteen(self):
        """The sharpest check available, and it is derivable by hand.

        Each side opens with two pieces at opposite corners. From a corner:
        3 adjacent empty cells, and 5 cells on the distance-2 ring that lie on
        the board - (0,2), (1,2), (2,0), (2,1), (2,2) relative to (0,0). Two
        corners, no overlap at ply 1, and clones deduplicate by destination:
            6 clone destinations + 10 jumps = 16.

        This is precisely the knight-jump detector. Of a corner's 5 jump cells,
        two - (1,2) and (2,1) - are knight-shaped. A generator that enumerates
        only straight and diagonal two-steps drops those, giving 3 jumps per
        corner and a total of 12 rather than 16.
        """
        self.assertEqual(self.stats.mean_by_ply[0], 16.0)

    def test_the_curve_rises_to_several_times_the_opening_width(self):
        # The flat-curve detector. Measured on this implementation: peak 73.7 at
        # ply 59, i.e. 4.6x the opening. A generator missing half the jump ring
        # would flatten this badly.
        first = self.stats.mean_by_ply[0]
        peak = max(self.stats.mean_by_ply)
        self.assertGreater(peak, 55.0, "mid-game peak far too low")
        self.assertGreater(peak / first, 3.0, "curve is too flat to be correct")

    def test_the_peak_is_in_the_middle_game_not_at_the_start(self):
        peak_ply = self.stats.mean_by_ply.index(max(self.stats.mean_by_ply))
        self.assertGreater(peak_ply, 20)
        self.assertLess(peak_ply, 120)

    def test_average_game_length_sits_between_the_reference_and_our_cap(self):
        # Measured: about 188 plies under random play, against the reference's
        # ~100 for stronger play and our own 300-ply hard cap. Random play makes
        # many unproductive jumps, which neither fill the board nor convert, so
        # games drag relative to the reference.
        self.assertGreater(self.stats.mean_length, 100.0)
        self.assertLess(self.stats.mean_length, 300.0)


if __name__ == "__main__":
    unittest.main()
