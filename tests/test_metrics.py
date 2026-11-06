import unittest

from evals.metrics import (MAX_CITATION_SECONDS, Span, citation_valid, entails_lite,
                           first_relevant_rank, mean_reciprocal_rank, missing_numbers,
                           overlap_seconds, rate, recall_at_k, spans_match, support_ratio)
from evals.text import content_tokens, tokenize

G = Span("v1", 10.0, 20.0)


class TestOverlap(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(overlap_seconds(G, G), 10.0)

    def test_touching_is_zero(self):
        self.assertEqual(overlap_seconds(G, Span("v1", 20.0, 30.0)), 0.0)
        self.assertFalse(spans_match(G, Span("v1", 20.0, 30.0)))

    def test_disjoint_is_zero(self):
        self.assertEqual(overlap_seconds(G, Span("v1", 40.0, 50.0)), 0.0)

    def test_other_video_is_zero(self):
        self.assertEqual(overlap_seconds(G, Span("v2", 10.0, 20.0)), 0.0)
        self.assertFalse(spans_match(G, Span("v2", 10.0, 20.0)))

    def test_zero_length_never_matches(self):
        self.assertFalse(spans_match(G, Span("v1", 15.0, 15.0)))
        self.assertFalse(spans_match(Span("v1", 5.0, 5.0), Span("v1", 5.0, 5.0)))

    def test_half_of_shorter_threshold(self):
        # 5 s overlap with a 10 s gold span: exactly half of the shorter span -> match
        self.assertTrue(spans_match(G, Span("v1", 15.0, 25.0)))
        # 4.9 s overlap -> no match
        self.assertFalse(spans_match(G, Span("v1", 15.1, 25.0)))

    def test_short_span_inside_long_span_matches(self):
        self.assertTrue(spans_match(Span("v1", 12.0, 13.0), G))


class TestRetrievalMetrics(unittest.TestCase):
    def test_rank(self):
        retrieved = [Span("v2", 10, 20), Span("v1", 30, 40), Span("v1", 11, 19)]
        self.assertEqual(first_relevant_rank(retrieved, G), 3)
        self.assertIsNone(first_relevant_rank(retrieved[:2], G))

    def test_recall_at_k_one_and_zero(self):
        self.assertEqual(recall_at_k([1, 1, 1], 1), 1.0)
        self.assertEqual(recall_at_k([None, None], 10), 0.0)
        # gold at rank k+1 does not count for recall@k
        self.assertEqual(recall_at_k([4], 3), 0.0)
        self.assertEqual(recall_at_k([3], 3), 1.0)
        self.assertEqual(recall_at_k([1, None, 2, 5], 3), 0.5)

    def test_mrr(self):
        self.assertEqual(mean_reciprocal_rank([1, 1], 10), 1.0)
        self.assertEqual(mean_reciprocal_rank([None, None], 10), 0.0)
        self.assertEqual(mean_reciprocal_rank([11], 10), 0.0)
        self.assertAlmostEqual(mean_reciprocal_rank([1, 2, None, 4], 10), (1 + 0.5 + 0 + 0.25) / 4)

    def test_empty_is_none(self):
        self.assertIsNone(recall_at_k([], 1))
        self.assertIsNone(mean_reciprocal_rank([], 10))
        self.assertIsNone(rate([]))


class TestCitationValidity(unittest.TestCase):
    def test_exact_cite_is_valid(self):
        self.assertTrue(citation_valid(G, G))

    def test_missing_cite_is_invalid(self):
        self.assertFalse(citation_valid(None, G))

    def test_wrong_video_or_place_is_invalid(self):
        self.assertFalse(citation_valid(Span("v2", 10, 20), G))
        self.assertFalse(citation_valid(Span("v1", 30, 40), G))

    def test_length_cap(self):
        at_cap = Span("v1", 0.0, MAX_CITATION_SECONDS)
        over_cap = Span("v1", 0.0, MAX_CITATION_SECONDS + 1)
        self.assertTrue(citation_valid(at_cap, G))
        self.assertFalse(citation_valid(over_cap, G))

    def test_whole_video_cite_is_invalid(self):
        self.assertFalse(citation_valid(Span("v1", 0.0, 3600.0), G))


class TestFaithfulness(unittest.TestCase):
    SRC = "The fix was to enable TCP keepalives on the client every sixty seconds."

    def test_verbatim_is_faithful(self):
        self.assertEqual(support_ratio(self.SRC, self.SRC), 1.0)
        self.assertTrue(entails_lite(self.SRC, self.SRC))

    def test_unrelated_is_zero(self):
        self.assertEqual(support_ratio("Bluetooth advertising channels", self.SRC), 0.0)
        self.assertFalse(entails_lite("Bluetooth advertising channels", self.SRC))

    def test_wrong_number_is_unfaithful(self):
        ans = "Enable TCP keepalives on the client every thirty seconds."
        self.assertEqual(missing_numbers(ans, self.SRC), ["thirty"])
        self.assertFalse(entails_lite(ans, self.SRC))
        self.assertFalse(entails_lite("Keepalives every 30 seconds.", self.SRC))

    def test_empty_answer_is_unfaithful(self):
        self.assertFalse(entails_lite("", self.SRC))
        self.assertFalse(entails_lite("   ", self.SRC))
        self.assertEqual(support_ratio("the of and", self.SRC), 0.0)

    def test_partial_support_threshold(self):
        # 4 of 5 content tokens supported -> 0.8, passes at the default 0.8
        ans = "client keepalives every sixty minutes"
        self.assertAlmostEqual(support_ratio(ans, self.SRC), 0.8)
        self.assertTrue(entails_lite(ans, self.SRC))
        self.assertFalse(entails_lite(ans, self.SRC, min_ratio=0.81))

    def test_rate(self):
        self.assertEqual(rate([True, True]), 1.0)
        self.assertEqual(rate([False, False]), 0.0)


class TestText(unittest.TestCase):
    def test_compounds_kept_and_split(self):
        toks = tokenize("Apply tcp.flags.reset == 1 and call tools/list")
        for t in ("tcp.flags.reset", "tcp", "flag", "reset", "1", "tools/list", "tool", "list"):
            self.assertIn(t, toks)

    def test_stopwords_dropped(self):
        self.assertEqual(content_tokens("What is the MTU of the link?"), ["mtu", "link"])


if __name__ == "__main__":
    unittest.main()
