"""Reference retriever: fixed-length time chunks scored with BM25 across all transcripts.

The repo has no retrieval step of its own. This one exists so retrieval can be measured;
it is a baseline, not a tuned system.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass

from evals.metrics import Span
from evals.text import QUESTION_STOPWORDS, STOPWORDS, content_tokens

CHUNK_SECONDS = 10.0


@dataclass(frozen=True)
class Chunk:
    video_id: str
    start: float
    end: float
    text: str
    segments: tuple  # ((start, end, text), ...)

    @property
    def span(self) -> Span:
        return Span(self.video_id, self.start, self.end)


def chunk_transcripts(transcripts: dict[str, list[dict]],
                      chunk_seconds: float = CHUNK_SECONDS) -> list[Chunk]:
    """Group consecutive segments until a chunk reaches chunk_seconds. No overlap."""
    chunks: list[Chunk] = []
    for vid in sorted(transcripts):
        buf: list[dict] = []
        for seg in transcripts[vid]:
            buf.append(seg)
            if buf[-1]["end"] - buf[0]["start"] >= chunk_seconds:
                chunks.append(_make(vid, buf))
                buf = []
        if buf:
            chunks.append(_make(vid, buf))
    return chunks


def _make(vid: str, segs: list[dict]) -> Chunk:
    return Chunk(vid, segs[0]["start"], segs[-1]["end"], " ".join(s["text"] for s in segs),
                 tuple((s["start"], s["end"], s["text"]) for s in segs))


class BM25:
    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.docs = [Counter(content_tokens(c.text, STOPWORDS)) for c in chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avg_len = sum(self.lengths) / len(self.lengths)
        df = Counter(t for d in self.docs for t in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int) -> list[tuple[Chunk, float]]:
        terms = set(content_tokens(query, QUESTION_STOPWORDS))
        scored = []
        for i, doc in enumerate(self.docs):
            score = 0.0
            norm = self.k1 * (1 - self.b + self.b * self.lengths[i] / self.avg_len)
            for t in terms:
                f = doc.get(t, 0)
                if f:
                    score += self.idf[t] * f * (self.k1 + 1) / (f + norm)
            scored.append((score, i))
        # Highest score first; ties broken by corpus order so results are deterministic.
        scored.sort(key=lambda x: (-x[0], x[1]))
        return [(self.chunks[i], round(s, 6)) for s, i in scored[:k]]
