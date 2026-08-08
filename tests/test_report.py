import unittest

from experiments import report


class CommentaryTest(unittest.TestCase):
    TEXT = "\n".join([
        "Preamble that belongs to no section.",
        "",
        "<!-- section: overview -->",
        "This run answers the width question.",
        "",
        "<!-- section: results -->",
        "<!-- TODO -->",
        "",
    ])

    def test_parses_a_filled_section(self):
        sections = report.parse_commentary(self.TEXT)
        self.assertEqual(sections["overview"],
                         "This run answers the width question.")

    def test_a_todo_only_section_counts_as_empty(self):
        sections = report.parse_commentary(self.TEXT)
        self.assertEqual(sections["results"], "")

    def test_a_filled_section_renders_its_prose(self):
        sections = report.parse_commentary(self.TEXT)
        self.assertEqual(report.commentary_for(sections, "overview"),
                         "This run answers the width question.")

    def test_an_empty_section_renders_a_visible_callout(self):
        sections = report.parse_commentary(self.TEXT)
        rendered = report.commentary_for(sections, "results")
        self.assertIn("COMMENTARY NEEDED", rendered)
        self.assertIn("results", rendered)

    def test_a_missing_section_renders_a_visible_callout(self):
        rendered = report.commentary_for({}, "limitations")
        self.assertIn("COMMENTARY NEEDED", rendered)

    def test_an_unknown_section_id_is_an_error(self):
        # A renamed report section must not silently orphan its prose.
        with self.assertRaises(ValueError):
            report.validate_commentary({"no-such-slot": "text"},
                                       report.SECTION_IDS)

    def test_every_known_id_validates(self):
        sections = dict((i, "x") for i in report.SECTION_IDS)
        report.validate_commentary(sections, report.SECTION_IDS)


if __name__ == "__main__":
    unittest.main()
