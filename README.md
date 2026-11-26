# youtube-knowledge

A small Python pipeline that pulls YouTube transcripts (videos, channels, playlists, search topics) into clean
JSONL, plus a written contract for extracting **cited** insights from them (tools, people, papers, links, action
items, each with a video id and a timestamp). It also ships an offline evaluation harness that prints its own
measured weaknesses next to its results.

## What is in the code and what is not

| Stage | What it does | In this repo |
|---|---|---|
| Ingest | `yt-dlp` for metadata and human or auto captions, `youtube-transcript-api` as the fallback. Resumable: videos already fetched are skipped. | code, `src/ingest.py` |
| Normalize | Raw captions to one JSONL record per video and one per transcript. | code, `src/normalize.py` |
| Extract | Turns one transcript into cited insights under the rules in `docs/extract_spec.md` ("cite or cut", no invented facts, links only if spoken or in the description). | **A written spec only.** I run it with Claude Code subagents. There is no extract code in `src/` and no provider switch to call; the `extract:` block in `config/config.yaml` is not read by any code yet. |
| Evaluate | A reference retrieval and answering path, scored on 50 labelled questions. | code, `evals/` |

## Quickstart

```bash
git clone https://github.com/Aeripsen/youtube-knowledge && cd youtube-knowledge
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python src/run.py --limit 1                           # fetch and normalize one video (needs the network, about 20 s)
python src/inspect_output.py                          # title, channel, caption source, segment count
```

Offline, no keys, no network:

```bash
python -m unittest discover -s tests -t .             # 37 tests
python -m evals.run --check                           # re-runs the evaluation, fails if it differs from the committed results
```

All four commands were run from a fresh clone on 2026-11-26 (Python 3.14, Windows): the ingest of one video returned
`{'auto_subs': 1}`, the 37 tests passed, and the evaluation matched the committed results. Outputs land in
`data/raw/` and `data/normalized/`, which are gitignored. Put your own sources in `data/input/` and options in
`config/config.yaml`. A `YOUTUBE_API_KEY` is only needed for the optional comments path, which is off by default.

## How it works

```
data/input/*  ->  INGEST  ->  data/raw/  ->  NORMALIZE  ->  data/normalized/  ->  EXTRACT (spec)  ->  data/insights/
```

Configuration over code edits (`config/config.yaml`), citations required (`docs/extract_spec.md`), and explicit
rules against low-quality output (`docs/anti_slop_rules.md`). The record schema is in `docs/data_schema.md`.

## Layout

- `config/config.yaml`: transcript priority, languages, delays, fields to extract
- `data/input/`: `videos.txt`, `channels.txt`, `playlists.txt`, `search-queries.txt`, `resources.md`
- `src/`: ingest, normalize, run, inspect_output
- `evals/` and `tests/`: the harness and its tests
- `docs/`: schema, extract spec, anti-slop rules, evaluation method

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

The ingest and normalize stages run end to end (checked on one video, 2026-11-26). The committed input lists are
example sources, mostly AI-agent and IoT talks. How good the subagent extraction output is has not been measured:
the harness above scores retrieval and answering, not the insight files.

## License

MIT, see `LICENSE`.
