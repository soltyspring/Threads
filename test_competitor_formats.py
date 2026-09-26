import unittest
from collections import Counter, defaultdict

import competitor_formats as formats


class CompetitorFormatTests(unittest.TestCase):
    def test_deterministic_balanced_unique_campaign(self):
        posts = formats.build_posts(120)
        self.assertEqual(posts, formats.build_posts(120))
        self.assertEqual(len({p["text"] for p in posts}), 120)
        self.assertEqual(set(Counter(p["theme"] for p in posts).values()), {10})
        self.assertEqual(sum(p["is_control"] for p in posts), 30)
        self.assertEqual(set(Counter(p["format"] for p in posts).values()), {30})

    def test_safe_width_metrics_and_length_coverage(self):
        posts = formats.build_posts(168)
        self.assertTrue({"short", "medium", "long"}.issubset(
            {p["length_bucket"] for p in posts}))
        for p in posts:
            self.assertLessEqual(p["utf16_length"], 500)
            self.assertEqual(p["codepoint_length"], len(p["text"]))
            self.assertEqual(p["utf16_length"], len(p["text"].encode("utf-16-le")) // 2)
            self.assertLessEqual(p["max_line_cells_estimate"], 40)
            self.assertLessEqual(p["codepoint_length"], 300)
            self.assertNotIn("\n\n\n", p["text"])
            self.assertNotIn("　　", p["text"])
            self.assertAlmostEqual(p["whitespace_ratio"],
                                   sum(c.isspace() for c in p["text"]) / len(p["text"]))

    def test_single_factor_pairs_and_exploratory_labels(self):
        groups = defaultdict(dict)
        for p in formats.build_posts(96):
            groups[p["pair_id"]][p["arm"]] = p
        for arms in groups.values():
            a, b, c, d = (arms[key] for key in "ABCD")
            self.assertTrue(a["family_complete"])
            self.assertEqual(a["factors"]["items"], b["factors"]["items"][:12])
            self.assertEqual(a["factors"]["items"], d["factors"]["items"])
            self.assertEqual(a["factors"]["gap"], d["factors"]["gap"])
            self.assertEqual(a["factors"]["columns_per_row"], d["factors"]["columns_per_row"])
            self.assertNotEqual(a["factors"]["title"], d["factors"]["title"])
            self.assertIn("multivariate_exploratory", b["comparison_design"])
            self.assertIsNone(b["controlled_factor"])
            self.assertEqual(c["comparison_design"], "multivariate_exploratory")
            self.assertIsNone(c["controlled_factor"])

    def test_exclusions_regenerate_coherent_families(self):
        original = formats.build_posts(96)
        excluded = {p["text"] for p in original}
        posts = formats.build_posts(96, exclude_texts=excluded)
        self.assertFalse(excluded.intersection(p["text"] for p in posts))
        self.assertEqual(len({p["text"] for p in posts}), 96)
        for p in posts:
            self.assertTrue(p["family_complete"])

    def test_arbitrary_counts_and_partial_family_metadata(self):
        for count in [0, 1, 11, 47, 118, 121]:
            posts = formats.build_posts(count)
            self.assertEqual(len(posts), count)
            if posts:
                counts = Counter(p["theme"] for p in posts)
                self.assertLessEqual(max(counts.values()) - min(counts.values()), 1)
                self.assertLessEqual(abs(sum(p["is_control"] for p in posts) - count / 4), 1)
        self.assertFalse(formats.build_posts(1)[0]["family_complete"])
        with self.assertRaises(ValueError):
            formats.build_posts(-1)
        with self.assertRaises(ValueError):
            formats.build_posts(True)
        with self.assertRaises(TypeError):
            formats.build_posts(1, "whole text")


if __name__ == "__main__":
    unittest.main()
