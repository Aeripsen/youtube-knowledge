"""Quick human-readable summary of the normalized output. Run from the subproject root."""
from __future__ import annotations

import json
from pathlib import Path

import config

norm = config.resolve_paths(config.load_config())["normalized_dir"]


def main() -> None:
    vf, tf = norm / "videos.jsonl", norm / "transcripts.jsonl"
    print("=== videos ===")
    for line in vf.read_text(encoding="utf-8").splitlines():
        v = json.loads(line)
        print(f"{v['video_id']} | {v['title']!r} | {v['channel']} | {v['upload_date']} "
              f"| {v['duration_seconds']}s | views={v['view_count']} | {v['transcript_status']}")
    print("\n=== transcripts ===")
    for line in tf.read_text(encoding="utf-8").splitlines():
        t = json.loads(line)
        print(f"{t['video_id']} | src={t['source']} | segs={t['segment_count']} | chars={len(t['full_text'])}")
        print(f"   {t['full_text'][:170]} ...")


if __name__ == "__main__":
    main()
