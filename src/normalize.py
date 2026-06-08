"""Normalize stage: raw artifacts -> validated JSONL (videos + transcripts).

Deterministic only (no LLM). Reads from disk, never from the network.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_TC = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.,](\d{3})")


def _secs(h, m, s, ms) -> float:
    return round(int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000, 3)


def parse_json3(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    segs = []
    for e in data.get("events", []):
        if "segs" not in e:
            continue
        text = "".join(s.get("utf8", "") for s in e["segs"]).strip()
        if not text:
            continue
        segs.append({
            "start": round(e.get("tStartMs", 0) / 1000, 3),
            "duration": round(e.get("dDurationMs", 0) / 1000, 3),
            "text": text,
        })
    return segs


def parse_vtt(path: Path) -> list[dict]:
    segs = []
    cur_start = cur_end = None
    buf: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = _TC.search(line)
        if m:
            if cur_start is not None and buf:
                segs.append({"start": cur_start, "duration": round(cur_end - cur_start, 3),
                             "text": " ".join(buf)})
            cur_start = _secs(*m.group(1, 2, 3, 4))
            cur_end = _secs(*m.group(5, 6, 7, 8))
            buf = []
        elif line.strip() and "WEBVTT" not in line and "-->" not in line and not line.strip().isdigit():
            clean = re.sub(r"<[^>]+>", "", line).strip()  # drop inline timing/format tags
            if clean:
                buf.append(clean)
    if cur_start is not None and buf:
        segs.append({"start": cur_start, "duration": round((cur_end or cur_start) - cur_start, 3),
                     "text": " ".join(buf)})
    # drop consecutive duplicate lines (auto-caption rolling repeats)
    out, prev = [], None
    for s in segs:
        if s["text"] != prev:
            out.append(s)
            prev = s["text"]
    return out


def _transcript(vdir: Path, vid: str, status: str) -> tuple[list[dict], str | None]:
    j3 = sorted(vdir.glob("*.json3"))
    vtt = sorted(vdir.glob("*.vtt"))
    tapi = vdir / f"{vid}.transcript_api.json"
    if j3:
        return parse_json3(j3[0]), status
    if vtt:
        return parse_vtt(vtt[0]), status
    if tapi.exists():
        return json.loads(tapi.read_text(encoding="utf-8")), "transcript_api"
    return [], None


def normalize_all(raw_dir: Path, norm_dir: Path) -> tuple[int, int]:
    norm_dir.mkdir(parents=True, exist_ok=True)
    per_video_dir = norm_dir / "transcripts"
    per_video_dir.mkdir(exist_ok=True)
    videos, transcripts = [], []
    for vdir in sorted(p for p in raw_dir.iterdir() if p.is_dir()):
        vid = vdir.name
        info_f = vdir / f"{vid}.info.json"
        if not info_f.exists():
            continue
        info = json.loads(info_f.read_text(encoding="utf-8", errors="ignore"))
        meta = {}
        if (vdir / "_ingest.json").exists():
            meta = json.loads((vdir / "_ingest.json").read_text(encoding="utf-8"))
        status = meta.get("transcript_status", "unknown")

        segs, tsource = _transcript(vdir, vid, status)
        ud = info.get("upload_date") or ""
        videos.append({
            "video_id": vid,
            "url": info.get("webpage_url"),
            "title": info.get("title"),
            "channel": info.get("channel") or info.get("uploader"),
            "channel_id": info.get("channel_id"),
            "upload_date": f"{ud[:4]}-{ud[4:6]}-{ud[6:8]}" if len(ud) == 8 else None,
            "duration_seconds": info.get("duration"),
            "view_count": info.get("view_count"),
            "description": info.get("description"),
            "language": info.get("language"),
            "source": "videos.txt",
            "transcript_status": status,
            "fetched_at": meta.get("fetched_at"),
            "raw_path": f"data/raw/{vid}",
        })
        if segs:
            transcripts.append({
                "video_id": vid,
                "title": info.get("title"),
                "url": info.get("webpage_url"),
                "source": tsource,
                "segment_count": len(segs),
                "segments": segs,
                "full_text": " ".join(s["text"] for s in segs),
            })
            # Per-video file = self-contained, lean input for the EXTRACT stage:
            # segments (text + timestamps for citations) + description (for links). No full_text.
            (per_video_dir / f"{vid}.json").write_text(json.dumps({
                "video_id": vid,
                "title": info.get("title"),
                "url": info.get("webpage_url"),
                "source": tsource,
                "description": info.get("description"),
                "segment_count": len(segs),
                "segments": segs,
            }, ensure_ascii=False), encoding="utf-8")

    (norm_dir / "videos.jsonl").write_text(
        "".join(json.dumps(v, ensure_ascii=False) + "\n" for v in videos), encoding="utf-8")
    (norm_dir / "transcripts.jsonl").write_text(
        "".join(json.dumps(t, ensure_ascii=False) + "\n" for t in transcripts), encoding="utf-8")
    return len(videos), len(transcripts)
