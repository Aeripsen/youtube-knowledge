import io
import json
import unittest

from evals.answerers import (Answer, AnthropicAnswerer, LLMJudge, anthropic_messages,
                             parse_answer)
from evals.metrics import Span
from evals.retrieve import Chunk
from evals.run import RESULTS_DIR, dumps, run, stub_result


class OracleAnswerer:
    """Answers with the reference answer and cites the gold span; refuses unanswerables."""
    name = "oracle"

    def __init__(self, questions):
        self.by_q = {q["question"]: q for q in questions}

    def answer(self, question, hits):
        q = self.by_q[question]
        if not q["answerable"]:
            return Answer(True, "", None)
        return Answer(False, q["answer"], Span(q["video_id"], q["span"]["start"], q["span"]["end"]))


class AlwaysRefuse:
    name = "always_refuse"

    def answer(self, question, hits):
        return Answer(True, "", None)


class TestRun(unittest.TestCase):
    def test_stub_is_deterministic_and_matches_committed_file(self):
        first = dumps(stub_result())
        self.assertEqual(first, dumps(stub_result()))
        committed = (RESULTS_DIR / "stub.json").read_text(encoding="utf-8")
        self.assertEqual(first, committed, "run `python -m evals.run` and commit evals/results/stub.json")

    def test_oracle_scores_one(self):
        from evals.golden import load_questions
        m = run(OracleAnswerer(load_questions()))["metrics"]["all"]
        self.assertEqual(m["answers"]["citation_validity"], 1.0)
        self.assertEqual(m["refusal"]["refusal_accuracy_unanswerable"], 1.0)
        self.assertEqual(m["refusal"]["false_refusal_rate_answerable"], 0.0)
        self.assertEqual(m["answers"]["contains_reference_key_terms"], 1.0)

    def test_always_refuse(self):
        m = run(AlwaysRefuse())["metrics"]["all"]
        self.assertEqual(m["refusal"]["refusal_accuracy_unanswerable"], 1.0)
        self.assertEqual(m["refusal"]["false_refusal_rate_answerable"], 1.0)
        self.assertEqual(m["n_answered"], 0)
        self.assertIsNone(m["answers"]["citation_validity"])


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_urlopen(reply_text, captured):
    def _open(req, timeout=None):
        captured.append(req)
        body = {"content": [{"type": "text", "text": reply_text}]}
        return FakeResponse(json.dumps(body).encode("utf-8"))
    return _open


CHUNKS = [Chunk("v1", 0.0, 10.0, "alpha", ()), Chunk("v1", 10.0, 20.0, "beta", ())]


class TestAnthropicPlumbing(unittest.TestCase):
    def test_request_shape(self):
        captured = []
        text = anthropic_messages("hi", "model-x", "key-123", base_url="https://example.test",
                                  urlopen=fake_urlopen("ok", captured))
        self.assertEqual(text, "ok")
        req = captured[0]
        self.assertEqual(req.full_url, "https://example.test/v1/messages")
        self.assertEqual(req.get_header("X-api-key"), "key-123")
        self.assertEqual(req.get_header("Anthropic-version"), "2023-06-01")
        body = json.loads(req.data)
        self.assertEqual(body["model"], "model-x")
        self.assertEqual(body["temperature"], 0)

    def test_parse_answer(self):
        a = parse_answer('{"refuse": false, "answer": "beta", "cite": "C2"}', CHUNKS)
        self.assertEqual((a.refused, a.text, a.cite), (False, "beta", Span("v1", 10.0, 20.0)))
        self.assertTrue(parse_answer('Sure: {"refuse": true}', CHUNKS).refused)
        # out of range cite id is kept as a missing citation, not repaired
        self.assertIsNone(parse_answer('{"refuse": false, "answer": "x", "cite": "C9"}', CHUNKS).cite)
        with self.assertRaises(ValueError):
            parse_answer("no json here", CHUNKS)

    def test_answerer_end_to_end_with_fake_http(self):
        captured = []
        ans = AnthropicAnswerer("m", "k", urlopen=fake_urlopen('{"refuse": false, "answer": "a", "cite": "C1"}', captured))
        out = ans.answer("q?", [(c, 1.0) for c in CHUNKS])
        self.assertEqual(out.cite, Span("v1", 0.0, 10.0))
        self.assertIn("[C2]", json.loads(captured[0].data)["messages"][0]["content"])

    def test_judge(self):
        self.assertTrue(LLMJudge("m", "k", urlopen=fake_urlopen("SUPPORTED", [])).supported("a", "b"))
        self.assertFalse(LLMJudge("m", "k", urlopen=fake_urlopen("NOT_SUPPORTED", [])).supported("a", "b"))


if __name__ == "__main__":
    unittest.main()
