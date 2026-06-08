"""Run the YouTube ingest -> normalize pipeline.

Usage (from projects/youtube-knowledge/):
    python src/run.py            # all videos in data/input/videos.txt
    python src/run.py --limit 3  # first 3 (for a quick test)
"""
from __future__ import annotations

import argparse
import time
from collections import Counter

import config
import ingest
import normalize
from tqdm import tqdm


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="process only the first N videos")
    ap.add_argument("--normalize-only", action="store_true",
                    help="skip ingest; re-normalize existing raw data")
    args = ap.parse_args()

    cfg = config.load_config()
    paths = config.resolve_paths(cfg)
    raw_dir, norm_dir = paths["raw_dir"], paths["normalized_dir"]
    raw_dir.mkdir(parents=True, exist_ok=True)

    if args.normalize_only:
        nv, nt = normalize.normalize_all(raw_dir, norm_dir)
        print(f"NORMALIZE: {nv} video records, {nt} transcripts -> {norm_dir}")
        return

    # collect unique video ids (dedup, preserve order)
    seen: dict[str, str] = {}
    for u in ingest.read_url_list(paths["input_dir"] / "videos.txt"):
        vid = ingest.extract_video_id(u)
        if vid and vid not in seen:
            seen[vid] = u
    if args.limit:
        seen = dict(list(seen.items())[: args.limit])
    print(f"INGEST: {len(seen)} unique videos")

    delay = cfg["ingest"].get("request_delay_seconds", 2)
    statuses = Counter()
    for vid, u in tqdm(seen.items(), desc="ingest"):
        try:
            st = ingest.fetch_video(vid, u, raw_dir, cfg)
        except Exception as e:  # never let one bad video stop the run
            st = "error"
            print(f"  ! {vid}: {e}")
        statuses[st] += 1
        time.sleep(delay)

    print("\nINGEST status:", dict(statuses))
    nv, nt = normalize.normalize_all(raw_dir, norm_dir)
    print(f"NORMALIZE: {nv} video records, {nt} transcripts -> {norm_dir}")


if __name__ == "__main__":
    main()
