# Data Schema

All normalized data is JSONL (one JSON object per line). Schemas are enforced in
code with pydantic so malformed records fail loudly instead of silently.

## `data/normalized/videos.jsonl` — one record per video

| field | type | notes |
|---|---|---|
| `video_id` | str | YouTube 11-char ID (primary key) |
| `url` | str | canonical watch URL |
| `title` | str | |
| `channel` | str | channel name |
| `channel_id` | str | |
| `upload_date` | str | ISO `YYYY-MM-DD` |
| `duration_seconds` | int | |
| `description` | str | full description text |
| `language` | str\|null | detected/declared language |
| `source` | str | which input list it came from (videos/playlist/channel) |
| `transcript_status` | str | `manual_subs` \| `auto_subs` \| `transcript_api` \| `unavailable` |
| `fetched_at` | str | ISO 8601 UTC timestamp |
| `raw_paths` | obj | paths to the immutable raw artifacts |

## `data/normalized/transcripts.jsonl` — one record per video's transcript

| field | type | notes |
|---|---|---|
| `video_id` | str | foreign key -> videos |
| `language` | str | |
| `source` | str | `manual_subs` \| `auto_subs` \| `transcript_api` |
| `segments` | list | ordered list of `{start, duration, text}` (seconds) |
| `full_text` | str | concatenated plain text |

## `data/normalized/comments.jsonl` — deferred (off by default)

| field | type | notes |
|---|---|---|
| `video_id` | str | foreign key |
| `comment_id` | str | |
| `author` | str | |
| `text` | str | |
| `like_count` | int | |
| `published_at` | str | ISO 8601 |
| `parent_id` | str\|null | null = top-level |

## `data/insights/<video_id>.json` — LLM-derived (extract stage)

Every list item carries a citation `{video_id, start}` so it traces back to the
exact moment in the source.

```json
{
  "video_id": "...",
  "provider": "claude_code",
  "summary": "...",
  "key_points":      [{"text": "...", "cite": {"video_id": "...", "start": 123.4}}],
  "tools_mentioned": [{"name": "...", "cite": {...}}],
  "people_mentioned":[{"name": "...", "cite": {...}}],
  "books_papers":    [{"title": "...", "cite": {...}}],
  "links_resources": [{"url": "...", "cite": {...}}],
  "action_items":    [{"text": "...", "cite": {...}}]
}
```
