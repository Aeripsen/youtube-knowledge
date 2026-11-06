"""Load the golden set: transcripts (parsed by the pipeline's own normalize.parse_vtt)
and labelled questions.

Print the parsed segments of one transcript, for labelling:
    python -m evals.golden g_tcp_resets
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = PROJECT_ROOT / "evals" / "golden"
TRANSCRIPT_DIR = GOLDEN_DIR / "transcripts"
QUESTIONS_FILE = GOLDEN_DIR / "questions.jsonl"

# normalize.py only uses the standard library. config.py is not imported on purpose:
# it needs yaml and dotenv, which the eval does not.
sys.path.insert(0, str(PROJECT_ROOT / "src"))
import normalize  # noqa: E402


def load_transcripts(directory: Path = TRANSCRIPT_DIR) -> dict[str, list[dict]]:
    """video_id -> segments [{start, end, text}], in time order."""
    out = {}
    for path in sorted(directory.glob("*.vtt")):
        segs = normalize.parse_vtt(path)
        out[path.stem] = [{"start": s["start"], "end": round(s["start"] + s["duration"], 3),
                           "text": s["text"]} for s in segs]
    return out


def load_questions(path: Path = QUESTIONS_FILE) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def text_in_range(segments: list[dict], start: float, end: float) -> str:
    """Text of every segment with positive overlap with [start, end)."""
    return " ".join(s["text"] for s in segments if min(s["end"], end) - max(s["start"], start) > 0)


def main() -> None:
    transcripts = load_transcripts()
    vid = sys.argv[1] if len(sys.argv) > 1 else None
    if vid not in transcripts:
        print("usage: python -m evals.golden <video_id>; available:", ", ".join(transcripts))
        sys.exit(2)
    for i, s in enumerate(transcripts[vid]):
        print(f"{i:3d}  {s['start']:8.3f} -> {s['end']:8.3f}  {s['text']}")


if __name__ == "__main__":
    main()
