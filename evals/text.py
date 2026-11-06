"""Tokenization shared by retrieval, the stub answerer and the faithfulness check.

Deliberately simple and deterministic: lowercase, keep dotted/dashed/slashed compounds
(tcp.flags.reset, 802.15.4, json-rpc, tools/list) as one token and also emit their parts,
strip a plural "s", drop a fixed stopword list.
"""
from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+(?:[./'-][a-z0-9]+)*")
_PARTS = re.compile(r"[./'-]")

STOPWORDS = frozenset("""
a an and are as at be been but by can could did do does for from had has have he her his
how i if in into is it its just me my of on or our she so than that the their them then
there these they this those to too was we were what when where which while who whom whose
why will with would you your about after before also only up out over under not no yes
""".split())

# Words that frame a question but carry no content to look up.
QUESTION_STOPWORDS = STOPWORDS | frozenset(
    "speaker speaker's usually normally often example demo use used using".split())

NUMBER_WORDS = frozenset("""
zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen
fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty
ninety hundred thousand million
""".split())


def _stem(tok: str) -> str:
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss") and not any(c.isdigit() for c in tok):
        return tok[:-1]
    return tok


def tokenize(text: str) -> list[str]:
    """All tokens in order, compounds followed by their parts. No stopword removal."""
    out: list[str] = []
    for raw in _TOKEN.findall(text.lower()):
        if raw.endswith("'s"):
            raw = raw[:-2]
        out.append(_stem(raw))
        if _PARTS.search(raw):
            out.extend(_stem(p) for p in _PARTS.split(raw) if p)
    return out


def content_tokens(text: str, stopwords: frozenset[str] = STOPWORDS) -> list[str]:
    return [t for t in tokenize(text) if t not in stopwords]


def is_number_token(tok: str) -> bool:
    return any(c.isdigit() for c in tok) or tok in NUMBER_WORDS
