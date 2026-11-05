"""Metric functions. Pure, deterministic, no I/O. Rules are documented in docs/EVAL.md.

A Span is (video_id, start, end) in seconds. Spans are half-open: [start, end).
"""
from __future__ import annotations

from typing import NamedTuple, Sequence

from evals.text import content_tokens, is_number_token


class Span(NamedTuple):
    video_id: str
    start: float
    end: float

    @property
    def length(self) -> float:
        return max(0.0, self.end - self.start)


# A span counts as matching a gold span when they share at least this fraction of the
# shorter of the two.
MIN_OVERLAP_FRACTION = 0.5
# A citation longer than this is too broad to check a claim against, so it is invalid.
MAX_CITATION_SECONDS = 60.0
# Fraction of an answer's content tokens that must appear in the source text.
MIN_SUPPORT_RATIO = 0.8


def overlap_seconds(a: Span, b: Span) -> float:
    """Length of the intersection. 0 for different videos or spans that only touch."""
    if a.video_id != b.video_id:
        return 0.0
    return max(0.0, min(a.end, b.end) - max(a.start, b.start))


def spans_match(a: Span, b: Span, min_fraction: float = MIN_OVERLAP_FRACTION) -> bool:
    """True when the overlap covers at least min_fraction of the shorter span.

    Zero-length spans never match, so a malformed span cannot score.
    """
    shorter = min(a.length, b.length)
    if shorter <= 0:
        return False
    return overlap_seconds(a, b) >= min_fraction * shorter


def first_relevant_rank(retrieved: Sequence[Span], gold: Span) -> int | None:
    """1-based rank of the first retrieved span that matches gold, or None."""
    for i, span in enumerate(retrieved, 1):
        if spans_match(span, gold):
            return i
    return None


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def recall_at_k(ranks: Sequence[int | None], k: int) -> float | None:
    """Share of questions whose gold span appears in the top k.

    Each question has one gold span, so per-question recall is 0 or 1.
    """
    return _mean([1.0 if r is not None and r <= k else 0.0 for r in ranks])


def mean_reciprocal_rank(ranks: Sequence[int | None], k_max: int) -> float | None:
    """Mean of 1/rank, counting a miss (or a rank beyond k_max) as 0."""
    return _mean([1.0 / r if r is not None and r <= k_max else 0.0 for r in ranks])


def citation_valid(cite: Span | None, gold: Span,
                   max_seconds: float = MAX_CITATION_SECONDS) -> bool:
    """A citation is valid when it names the gold video, is at most max_seconds long,
    and matches the gold span under spans_match."""
    if cite is None or cite.length > max_seconds:
        return False
    return spans_match(cite, gold)


def support_ratio(answer: str, source: str) -> float:
    """Share of the answer's distinct content tokens that occur in the source. 0 if none."""
    ans = set(content_tokens(answer))
    if not ans:
        return 0.0
    src = set(content_tokens(source))
    return len(ans & src) / len(ans)


def missing_numbers(answer: str, source: str) -> list[str]:
    """Number tokens (digits or number words) in the answer that the source lacks."""
    src = set(content_tokens(source))
    return sorted({t for t in content_tokens(answer) if is_number_token(t) and t not in src})


def entails_lite(answer: str, source: str, min_ratio: float = MIN_SUPPORT_RATIO) -> bool:
    """Deterministic entailment-lite: enough content-token support and no unsupported number.

    This checks lexical support only. It cannot see negation, reordering or paraphrase.
    """
    if not answer or not answer.strip():
        return False
    return support_ratio(answer, source) >= min_ratio and not missing_numbers(answer, source)


def rate(flags: Sequence[bool]) -> float | None:
    """Share of True values, or None when there is nothing to score."""
    return _mean([1.0 if f else 0.0 for f in flags])
