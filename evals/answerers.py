"""Answer providers for the eval, plus the optional LLM judge.

stub       Offline and deterministic. Picks the retrieved segment that covers the most
           question terms, returns its text verbatim and cites that segment. Refuses when
           retrieval or term coverage is weak. It is extractive, so it cannot paraphrase
           or hallucinate; that makes it a floor for citation and refusal, not a model.
anthropic  Calls the Anthropic Messages API with the top retrieved chunks. Needs
           ANTHROPIC_API_KEY and a model id from --model or YK_EVAL_MODEL.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from dataclasses import dataclass

from evals.metrics import Span
from evals.retrieve import BM25, Chunk
from evals.text import QUESTION_STOPWORDS, content_tokens

# Chosen on the dev split only by python -m evals.tune (see docs/EVAL.md, "Tuning").
STUB_MIN_SCORE = 4.0
STUB_MIN_COVERAGE = 0.3
STUB_CANDIDATE_CHUNKS = 3


@dataclass
class Answer:
    refused: bool
    text: str
    cite: Span | None


class StubAnswerer:
    name = "stub"

    def __init__(self, min_score: float = STUB_MIN_SCORE,
                 min_coverage: float = STUB_MIN_COVERAGE,
                 candidate_chunks: int = STUB_CANDIDATE_CHUNKS):
        self.min_score = min_score
        self.min_coverage = min_coverage
        self.candidate_chunks = candidate_chunks

    def answer(self, question: str, hits: list[tuple[Chunk, float]]) -> Answer:
        if not hits or hits[0][1] < self.min_score:
            return Answer(True, "", None)
        q_terms = set(content_tokens(question, QUESTION_STOPWORDS))
        best = None  # (coverage, -rank, -start) so max() is deterministic
        for rank, (chunk, _score) in enumerate(hits[: self.candidate_chunks]):
            for start, end, text in chunk.segments:
                cov = len(q_terms & set(content_tokens(text))) / len(q_terms) if q_terms else 0.0
                key = (cov, -rank, -start)
                if best is None or key > best[0]:
                    best = (key, Answer(False, text, Span(chunk.video_id, start, end)))
        if best is None or best[0][0] < self.min_coverage:
            return Answer(True, "", None)
        return best[1]


# ---------------------------------------------------------------- real provider

ANTHROPIC_VERSION = "2023-06-01"


def anthropic_messages(prompt: str, model: str, api_key: str, max_tokens: int = 400,
                       base_url: str | None = None, urlopen=urllib.request.urlopen) -> str:
    """One Messages API call at temperature 0. Returns the concatenated text blocks."""
    base = (base_url or os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")
    body = json.dumps({
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(f"{base}/v1/messages", data=body, method="POST", headers={
        "content-type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": ANTHROPIC_VERSION,
    })
    with urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


def _first_json_object(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError(f"no JSON object in model output: {text[:200]!r}")
    return json.loads(m.group(0))


ANSWER_PROMPT = """Answer the question using only the transcript excerpts below.
Each excerpt has an id in square brackets.

{excerpts}

Question: {question}

Rules:
- If the excerpts do not state the answer, refuse. Do not use outside knowledge.
- Otherwise answer in one short sentence and cite the single excerpt id that supports it.

Reply with only a JSON object, one of:
{{"refuse": true}}
{{"refuse": false, "answer": "...", "cite": "C1"}}"""


class AnthropicAnswerer:
    name = "anthropic"

    def __init__(self, model: str, api_key: str, context_chunks: int = 5, urlopen=urllib.request.urlopen):
        self.model, self.api_key = model, api_key
        self.context_chunks = context_chunks
        self.urlopen = urlopen

    def answer(self, question: str, hits: list[tuple[Chunk, float]]) -> Answer:
        chunks = [c for c, _ in hits[: self.context_chunks]]
        excerpts = "\n".join(f"[C{i}] ({c.video_id} {c.start:.1f}s-{c.end:.1f}s) {c.text}"
                             for i, c in enumerate(chunks, 1))
        raw = anthropic_messages(ANSWER_PROMPT.format(excerpts=excerpts, question=question),
                                 self.model, self.api_key, urlopen=self.urlopen)
        return parse_answer(raw, chunks)


def parse_answer(raw: str, chunks: list[Chunk]) -> Answer:
    """Map the model's JSON reply to an Answer. A bad or missing cite id gives cite=None,
    which scores as an invalid citation rather than being repaired."""
    obj = _first_json_object(raw)
    if obj.get("refuse") is True:
        return Answer(True, "", None)
    cite = None
    m = re.fullmatch(r"C(\d+)", str(obj.get("cite", "")).strip())
    if m and 1 <= int(m.group(1)) <= len(chunks):
        cite = chunks[int(m.group(1)) - 1].span
    return Answer(False, str(obj.get("answer", "")), cite)


JUDGE_PROMPT = """You are checking whether an answer is supported by a source passage.

Source passage:
{source}

Answer:
{answer}

Is every factual claim in the answer stated in the source passage? Reply with exactly one
word: SUPPORTED or NOT_SUPPORTED."""


class LLMJudge:
    """Second opinion on faithfulness. Off by default; never replaces the deterministic check."""

    def __init__(self, model: str, api_key: str, urlopen=urllib.request.urlopen):
        self.model, self.api_key, self.urlopen = model, api_key, urlopen

    def supported(self, answer: str, source: str) -> bool:
        raw = anthropic_messages(JUDGE_PROMPT.format(source=source, answer=answer),
                                 self.model, self.api_key, max_tokens=10, urlopen=self.urlopen)
        word = raw.strip().upper()
        return word.startswith("SUPPORTED")
