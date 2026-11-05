"""Checks that the golden set follows the labelling guide in docs/EVAL.md."""
import unittest
from collections import Counter

from evals.golden import load_questions, load_transcripts, text_in_range
from evals.text import content_tokens


class TestGoldenSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transcripts = load_transcripts()
        cls.questions = load_questions()

    def test_counts(self):
        c = Counter(q["answerable"] for q in self.questions)
        self.assertGreaterEqual(c[True], 40)
        self.assertEqual(c[False], 10)

    def test_ids_unique_and_splits_known(self):
        ids = [q["id"] for q in self.questions]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(q["split"] in ("dev", "heldout") for q in self.questions))
        held = Counter((q["answerable"], q["split"]) for q in self.questions)
        self.assertGreater(held[(True, "heldout")], 0)
        self.assertGreater(held[(False, "heldout")], 0)

    def test_spans_on_segment_boundaries(self):
        for q in self.questions:
            if not q["answerable"]:
                continue
            segs = self.transcripts[q["video_id"]]
            starts = {s["start"] for s in segs}
            ends = {s["end"] for s in segs}
            with self.subTest(q=q["id"]):
                self.assertLess(q["span"]["start"], q["span"]["end"])
                self.assertIn(q["span"]["start"], starts)
                self.assertIn(q["span"]["end"], ends)

    def test_key_terms_in_span_text(self):
        for q in self.questions:
            if not q["answerable"]:
                continue
            span_tokens = set(content_tokens(
                text_in_range(self.transcripts[q["video_id"]], q["span"]["start"], q["span"]["end"])))
            for term in q["key_terms"]:
                with self.subTest(q=q["id"], term=term):
                    self.assertTrue(set(content_tokens(term)) <= span_tokens)

    def test_reference_answer_contains_key_terms(self):
        for q in self.questions:
            if q["answerable"]:
                answer_tokens = set(content_tokens(q["answer"]))
                for term in q["key_terms"]:
                    with self.subTest(q=q["id"], term=term):
                        self.assertTrue(set(content_tokens(term)) <= answer_tokens)

    def test_unanswerable_terms_absent_everywhere(self):
        corpus = " ".join(s["text"] for segs in self.transcripts.values() for s in segs).lower()
        for q in self.questions:
            if q["answerable"]:
                continue
            self.assertIsNone(q["span"])
            for term in q["absent_terms"]:
                with self.subTest(q=q["id"], term=term):
                    self.assertNotIn(term.lower(), corpus)


if __name__ == "__main__":
    unittest.main()
