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

## Status
Working end to end on a real backlog of AI-agent and IoT/Wireshark talks. The committed input lists
are the example sources; pipeline outputs are gitignored.

## License
MIT — see `LICENSE`.
