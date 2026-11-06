# youtube-knowledge

A small, config-driven Python pipeline that turns a list of YouTube videos, channels, and search
topics into **cited, structured insights** (tools, people, books/papers, links, action items).
Built to digest a large backlog of technical talks without hand-watching every one.

## Why it exists
Watching dozens of long technical videos to extract "what tool did they recommend, what's the
actual takeaway" does not scale. This pipeline ingests sources, pulls the best available transcript,
normalizes it, and asks an LLM to extract insights **with citations** (every claim carries its
`video_id` + timestamp), so the output is checkable rather than vibes.

## How it works
```
INGEST  ->  NORMALIZE  ->  EXTRACT
```
1. **Ingest** (`src/ingest.py`) — `yt-dlp` for metadata + human/auto captions, with
   `youtube-transcript-api` as a fallback. Idempotent and resumable (skips already-fetched).
2. **Normalize** (`src/normalize.py`) — raw captions to clean JSONL transcripts.
3. **Extract** (`src/run.py`) — an LLM produces structured, **cited** insights per the schema in
   `docs/data_schema.md`. The provider is pluggable (`config.yaml` -> `extract.provider`) so the
   same pipeline can run against different models and cross-check them.

Design choices: configuration over code edits (`config/config.yaml`), citations required
(`docs/extract_spec.md`), and explicit anti-low-quality-output rules (`docs/anti_slop_rules.md`).

## Layout
- `config/config.yaml` — transcript priority, languages, provider, fields to extract
- `data/input/` — what to fetch: `videos.txt`, `channels.txt`, `playlists.txt`,
  `search-queries.txt` (topics resolved to real videos), `resources.md` (non-video docs/repos)
- `data/raw/` -> `data/normalized/` -> `data/insights/` — pipeline stages (gitignored outputs)
- `src/` — pipeline code
- `docs/` — `data_schema.md`, `extract_spec.md`, `anti_slop_rules.md`

## Run
```bash
pip install yt-dlp youtube-transcript-api pyyaml
# put sources in data/input/, set options in config/config.yaml
python src/run.py
```
A `YOUTUBE_API_KEY` (repo-root `.env`) is only needed for the optional comments/API-metadata path.
No secrets are committed.

## Evaluation
`make eval` (or `python -m evals.run`) scores retrieval, citations, faithfulness and refusal on
a labelled set. It runs offline with a stub answerer, needs no API key, and gives the same
output every run. `make eval-llm` runs a real provider when `ANTHROPIC_API_KEY` and
`YK_EVAL_MODEL` are set. Method, labelling guide and metric rules: `docs/EVAL.md`.

What it measures: `src/` has no retrieval or question-answering step, so the harness adds a
reference one (BM25 over 10 s transcript chunks, then an answerer that cites a time range) and
measures that. It does not score the extract stage's insight files.

### Results (stub answerer, offline)
From `evals/results/stub.json`. Thresholds were chosen on the dev split, so the held-out
column is the honest one.

| metric | all | held-out |
|---|---|---|
| questions (answerable / unanswerable) | 40 / 10 | 16 / 5 |
| retrieval recall@1 | 0.725 | 0.6875 |
| retrieval recall@3 | 0.90 | 0.875 |
| retrieval recall@5 | 0.95 | 1.0 |
| retrieval MRR@10 | 0.8263 | 0.799 |
| answered (of answerable) | 38 | 15 |
| citation validity | 0.7632 | 0.6667 |
| faithfulness to own citation (deterministic) | 1.0 | 1.0 |
| answer supported by gold span (deterministic) | 0.7895 | 0.7333 |
| answer contains reference key terms | 0.7895 | 0.7333 |
| refusal accuracy on unanswerable | 0.30 | 0.0 |
| false refusal rate on answerable | 0.05 | 0.0625 |

How to read it:
- Refusal is the weak point. The stub refused 3 of 10 unanswerable questions overall and none
  of the 5 held-out ones. Its refusal rule is lexical, and the unanswerable questions are hard
  negatives that share words with the transcripts, so it answers them with a related sentence.
- About a quarter of answered questions (a third on held-out) cite the wrong place. Causes
  seen in the per-question rows: picking a different segment of the right video (7 cases), citing
  a different video (1 case),
  and once citing the 10 ms repeat cue that follows a rolling auto-caption line (correct text,
  but the time range sits just after the spoken line, so the rule scores it invalid).
- Faithfulness to its own citation is 1.0 only because the stub copies the segment it cites.
  That number says nothing about a generating model. The gold-span number is the one to use.
- The real-provider path and the LLM judge were not run for these results (no API key in the
  environment where they were produced). Their request and parsing code is covered by unit
  tests with a mocked HTTP call.

Limits:
- Small set: 50 questions over 4 transcripts of 2 to 3 minutes, 48 chunks in total.
  recall@10 is 1.0 but covers about a fifth of the corpus, so it is close to meaningless here.
- One labeller, an AI model (Claude), which also wrote the transcripts. No second annotator,
  no agreement figure. Same-author text and questions probably flatter lexical retrieval.
- The transcripts are original text written for this repo. Three are clean captions and one
  imitates auto-captions. None has real mistranscriptions.
- It does not show how well the extract stage's insights are cited, or how a real model
  answers.

Run the tests with `make test` (standard library only).

## Status
Working end to end on a real backlog of AI-agent and IoT/Wireshark talks. The committed input lists
are the example sources; pipeline outputs are gitignored.

## License
MIT — see `LICENSE`.
