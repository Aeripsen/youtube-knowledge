# Evaluation harness

This harness measures retrieval quality, citation validity, answer faithfulness and refusal
on a small labelled set. Run it with `make eval` or `python -m evals.run`. It works offline
with no API key, and the offline run is deterministic.

## What is being measured

The pipeline in `src/` ingests and normalizes transcripts. It has no retrieval or
question-answering code, and the extract stage in `docs/extract_spec.md` is run by
Claude Code subagents outside this repo's code. That leaves nothing in `src/` that answers
a question, so the harness adds a small reference path and measures it:

1. Transcripts are parsed by the pipeline's own `normalize.parse_vtt`.
2. `evals/retrieve.py` splits each transcript into chunks of consecutive segments, each at
   least 10 s long and not overlapping, and ranks them with BM25 across all transcripts.
3. An answerer (`evals/answerers.py`) returns an answer, a cited time range
   `(video_id, start, end)`, or a refusal.
   - `stub` (default, offline): picks the segment in the top 3 chunks that covers the most
     question terms and returns its text verbatim with that segment as the citation. It
     refuses when the top BM25 score is below 4.0 or term coverage is below 0.3.
   - `anthropic`: sends the top 5 chunks to the Messages API and asks for JSON with an
     answer and one chunk id as the citation, or a refusal.

The citation contract matches the extract spec (`video_id` plus timestamp). The harness
does not score files in `data/insights/`; see "Not covered".

## Golden set

- `evals/golden/transcripts/*.vtt`: four short transcripts, 25 spoken lines each, between
  2 and 3 minutes long. Topics follow the repo's backlog: TCP resets in Wireshark, BLE
  GATT, Zigbee sniffing, MCP basics. `g_zigbee_sniff` is written in YouTube auto-caption
  form (lowercase, no punctuation, two-line rolling cues with inline word timing and 10 ms
  repeat cues), so it goes through the messy path of `parse_vtt`. The other three are
  clean manual captions.
- `evals/golden/questions.jsonl`: 50 questions. 40 are answerable, with a labelled
  supporting span. 10 are unanswerable: on topic, but the answer is not in any transcript.

All transcripts and questions were written for this repo by an AI model (Claude), which
also did the labelling. There is one labeller and no second annotator, so there is no
agreement figure. The material is original text, not copied from any video, so it can be
committed under the repo's MIT license.

### Record format

```json
{"id": "a01", "video_id": "g_tcp_resets", "question": "...", "answerable": true,
 "span": {"start": 20.715, "end": 25.715}, "answer": "tcp.flags.reset == 1",
 "key_terms": ["tcp.flags.reset"], "split": "dev"}
{"id": "u01", "video_id": "g_tcp_resets", "question": "...", "answerable": false,
 "span": null, "answer": null, "absent_terms": ["release"], "split": "dev"}
```

### Labelling guide

Answerable questions:

1. Read the parsed segments, not the raw VTT: `python -m evals.golden <video_id>`. Rolling
   auto-captions keep partial repeats after parsing, so raw cue times differ from what
   the pipeline sees.
2. Write the question in your own words. Avoid copying the transcript phrasing where a
   natural paraphrase exists, so retrieval is not just string matching.
3. The answer must be stated in the transcript, not inferred or taken from outside
   knowledge.
4. `span` is the smallest run of consecutive parsed segments that contains everything
   needed to answer. `start` is the first segment's start and `end` is the last segment's
   end, copied exactly. For rolling auto-captions, use the segment in which the line is
   first spoken (the long cue), not the 10 ms repeat cue that follows it.
5. `answer` is a short reference answer. `key_terms` are one to three words or phrases
   that any correct answer must contain, and that appear in both the span text and the
   reference answer, in the same form (for example both in words, not one in digits).
6. Assign `split`. Within each transcript, questions 3, 6, 8 and 10 are `heldout` and the
   rest are `dev`.

Unanswerable questions:

1. The question must be on topic for one transcript and share vocabulary with it, so it is
   a hard negative (for example "What brand of light bulb was used in the demo?" when the
   transcript mentions a light bulb but no brand).
2. The answer must not be stated or inferable from any transcript in the set.
3. `absent_terms` lists words that would have to appear in an answer, and they must not
   occur anywhere in the corpus (case-insensitive substring check).
4. Odd-numbered unanswerables are `dev`, even-numbered are `heldout`.

`tests/test_golden.py` enforces the mechanical parts: the counts, span edges on parsed
segment boundaries, key terms present in both span and reference answer, and absent terms
missing from the corpus.

## Metrics

All rules are in `evals/metrics.py` and tested in `tests/test_metrics.py`. Spans are
half-open `[start, end)` in seconds.

**Span match.** Two spans match when they are in the same video and their overlap is at
least half the length of the shorter span. Spans that only touch overlap by 0. Zero-length
spans never match.

**Retrieval.** For each answerable question, the rank of the first retrieved chunk that
matches the gold span.
- `recall@k`: share of answerable questions with that rank at most k. One gold span per
  question, so this is a hit rate. k = 1, 3, 5, 10.
- `mrr@10`: mean of 1/rank, with misses and ranks above 10 counted as 0.

**Citation validity.** For each answerable question that was not refused: the citation is
valid if it is in the gold video, is at most 60 s long, and matches the gold span under
the span match rule. The length cap stops a whole-video citation from passing. No LLM is
involved.

**Faithfulness (deterministic, entailment-lite).** The answer's distinct content tokens
(lowercased, stopwords removed, plural "s" stripped) are compared with a source text. The
answer passes if at least 80% of its tokens occur in the source and every number in it,
in digits or words, occurs in the source. Reported against two sources:
- `faithfulness_to_cited_span`: the text of the segments under the answer's own citation.
  For the stub this is 1.0 by construction, because it copies a segment and cites that
  same segment. It becomes informative for a generating model.
- `supported_by_gold_span`: the text under the labelled gold span. For the stub this is the
  informative number.

The check is lexical. It does not see negation, word order or paraphrase, so a fluent
paraphrase can fail and a wrong sentence built from source words can pass.

**Faithfulness (LLM judge, optional second opinion).** With `--llm-judge`, a model is asked
whether every claim in the answer is stated in the cited text. It is off by default,
needs an API key, and is reported under a key starting with `SECOND_OPINION_`. It never
replaces the deterministic check.

**Key terms.** `contains_reference_key_terms`: share of answered questions whose answer
contains every labelled key term. A rough correctness signal.

**Refusal.** `refusal_accuracy_unanswerable` is the share of unanswerable questions that
were refused. It is always reported next to `false_refusal_rate_answerable`, because
refusing everything scores 1.0 on the first.

Every metric is reported for `all`, `dev` and `heldout`. Answer metrics use answered
answerable questions as the denominator, and the results file gives that count as
`n_answered`.

## Tuning

The stub has two thresholds. `python -m evals.tune` sweeps a fixed grid on the **dev split
only** and picks the pair that maximizes the mean of refusal accuracy and
(1 minus false refusal rate), breaking ties toward smaller values. The chosen pair
(min score 4.0, min coverage 0.3) is hard-coded in `evals/answerers.py`. The chunk length,
BM25 parameters and metric thresholds were set before any run and were not tuned. The
held-out split was not used for any choice.

## Running

```bash
make eval          # offline stub, writes evals/results/stub.json
make eval-check    # exit 1 if a fresh stub run differs from the committed file
make test          # unit tests, standard library only
export ANTHROPIC_API_KEY=...  YK_EVAL_MODEL=<model id>
make eval-llm      # real provider plus LLM judge, writes evals/results/anthropic+judge.json
```

The eval uses only the Python standard library. No model id is hard-coded: pass `--model`
or set `YK_EVAL_MODEL`.

## Not covered

- The extract stage. Insight files from Claude Code runs are not scored. A next step is a
  gold-free check that each insight's `cite.start` falls in a segment whose text contains
  the insight's key words.
- Real captions. Three of four transcripts are clean text, and none has real
  mistranscriptions.
- Scale. 48 chunks in total, so recall@10 covers about a fifth of the corpus and is close
  to trivial. recall@1, recall@3 and MRR carry the signal.
- Independence. One AI author wrote both the transcripts and the questions, which probably
  makes lexical retrieval look better than it would on real talks.
