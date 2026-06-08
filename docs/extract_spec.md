# Extract spec (insight contract)

The contract every EXTRACT run follows (subagents now; API later). Goal: turn one
transcript into structured, **cited** insights with zero fabrication.

## Input (per video — self-contained, read only this one file)
`data/normalized/transcripts/<video_id>.json`:
`{video_id, title, url, source, description, segment_count, segments[]}`
where each segment is `{start, duration, text}` (start = seconds). The `description`
is the video's YouTube description (use it for links).

## Output
Write `data/insights/<video_id>.json`:

```json
{
  "video_id": "...",
  "provider": "claude_code",
  "title": "...",
  "url": "...",
  "summary": "2-4 sentences, plain and specific.",
  "key_points":       [{"text": "...", "cite": {"video_id": "...", "start": 12.3}}],
  "tools_mentioned":  [{"name": "...", "note": "what it's for (only if stated)", "cite": {...}}],
  "people_mentioned": [{"name": "...", "note": "who/why (only if stated)", "cite": {...}}],
  "books_papers":     [{"title": "...", "cite": {...}}],
  "links_resources":  [{"url": "...", "cite": {"video_id": "...", "source": "description"}}],
  "action_items":     [{"text": "...", "cite": {...}}],
  "low_confidence": false
}
```

`cite` = `{video_id, start}` for anything from the spoken transcript (start = the
segment time it's mentioned). For links taken from the description, use
`{video_id, source: "description"}` (no start).

## Rules (from anti_slop_rules.md)
1. **Cite or cut.** Every list item carries a `cite`. No citation → drop it.
2. **No invented facts.** Extract only what is actually said/written. Don't guess
   authors, don't add outside knowledge, don't pad.
3. **Links.** Include verbatim URLs that are (a) spoken/shown in the transcript, or
   (b) present in the `description`. Never construct or complete a URL.
4. **books_papers** includes books, papers, AND named courses/learning resources.
5. **Host/speaker exclusion.** The narrator/host themselves (incl. names used to
   address them) is NOT a `people_mentioned`. Only third parties discussed.
6. **Normalize obvious caption errors.** When a name/tool is clearly an
   auto-caption mistranscription of a well-known entity, use its canonical form
   ("Claw/Cloth Code" → "Claude Code", "MC3" → "MCP", "Enthropic" → "Anthropic",
   "NA10/NAN" → "n8n", "Codeex" → "Codex"). If you are NOT confident it's a known
   entity, keep the spoken form. Never invent a tool that wasn't referred to.
7. **Empty is valid.** Nothing of a kind mentioned → `[]`. No filler.
8. **Low confidence.** Set `low_confidence: true` only if captions are too garbled to trust.
9. Keep context lean — read only the target video's file.
