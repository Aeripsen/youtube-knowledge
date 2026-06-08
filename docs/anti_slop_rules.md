# Anti-Slop Rules

Rules that keep this knowledge base trustworthy. Apply to every extract run.

1. **Cite or cut.** Every key point, tool, person, book, link, and action item
   must carry a citation (`video_id` + timestamp). If a claim can't be traced to
   the transcript, it does not go in the output.
2. **No invented facts.** Extract only what is actually said. Do not "enrich" with
   outside knowledge, do not guess a book's author, do not normalize a tool name
   to one the speaker didn't use. Unknown = leave blank, don't fabricate.
3. **Quote links, don't synthesize them.** URLs come from the description or
   transcript text verbatim. Never construct a plausible-looking URL.
4. **Deterministic work stays in code.** Counting, dedup, metadata, parsing — never
   ask the LLM to do what code does reliably.
5. **Separate raw / normalized / insight.** Never let the model rewrite raw data.
   It reads normalized text and writes insights; the source is untouched.
6. **Empty is a valid answer.** A video with no tools mentioned gets an empty list,
   not a padded one. No filler, no "here are some related tools you might like."
7. **Flag low confidence.** If the transcript is auto-generated and garbled, mark
   the insight `low_confidence` rather than guessing through it.
8. **Failures are visible.** Missing transcripts → `transcript_status = unavailable`.
   Never silently drop a video or pretend a fetch succeeded.
9. **Cross-check at scale.** When multiple providers are enabled, disagreements
   between models are surfaced, not averaged away.
