"""Ingest stage: fetch raw, immutable artifacts for each video.

Transcript priority: yt-dlp manual subs -> yt-dlp auto subs -> youtube-transcript-api.
Idempotent: a video whose raw artifacts already exist is skipped. Failures are
recorded as transcript_status, never silently dropped.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

VIDEO_ID_RE = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")


def extract_video_id(url: str) -> str | None:
    m = VIDEO_ID_RE.search(url)
    if m:
        return m.group(1)
    s = url.strip()
    return s if re.fullmatch(r"[A-Za-z0-9_-]{11}", s) else None


def read_url_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line.split()[0])  # strip any inline "# comment"
    return out


def _ydl_opts(out_dir: Path, langs: list[str], auto: bool, cfg: dict) -> dict:
    opts = {
        "skip_download": True,            # never fetch the video itself
        "writeinfojson": True,
        "writedescription": True,
        "writesubtitles": not auto,
        "writeautomaticsub": auto,
        "subtitleslangs": langs,
        "subtitlesformat": "json3/vtt",   # json3 = clean structured timing
        "outtmpl": str(out_dir / "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "ignoreerrors": True,
        "retries": cfg["ingest"].get("max_retries", 3),
    }
    if cfg["ingest"].get("use_browser_cookies"):
        opts["cookiesfrombrowser"] = (cfg["ingest"].get("cookies_from_browser", "chrome"),)
    return opts


def _has_subs(d: Path) -> bool:
    return any(d.glob("*.json3")) or any(d.glob("*.vtt"))


def fetch_video(video_id: str, url: str, raw_dir: Path, cfg: dict) -> str:
    """Fetch one video's raw artifacts. Returns transcript_status."""
    langs = cfg["ingest"]["subtitle_languages"]
    vdir = raw_dir / video_id
    vdir.mkdir(parents=True, exist_ok=True)
    marker = vdir / "_ingest.json"

    if cfg["ingest"].get("skip_already_fetched") and marker.exists():
        return json.loads(marker.read_text(encoding="utf-8")).get("transcript_status", "unknown")

    status = "unavailable"

    # Pass A: metadata + description + manual subs
    with yt_dlp.YoutubeDL(_ydl_opts(vdir, langs, auto=False, cfg=cfg)) as ydl:
        ydl.download([url])
    if _has_subs(vdir):
        status = "manual_subs"
    else:
        # Pass B: auto-generated subs
        with yt_dlp.YoutubeDL(_ydl_opts(vdir, langs, auto=True, cfg=cfg)) as ydl:
            ydl.download([url])
        if _has_subs(vdir):
            status = "auto_subs"
        else:
            # Fallback: youtube-transcript-api (clean segments)
            try:
                fetched = YouTubeTranscriptApi().fetch(video_id, languages=langs)
                data = [{"start": s.start, "duration": s.duration, "text": s.text} for s in fetched]
                (vdir / f"{video_id}.transcript_api.json").write_text(
                    json.dumps(data, ensure_ascii=False), encoding="utf-8")
                status = "transcript_api"
            except Exception:
                status = "unavailable"

    marker.write_text(json.dumps({
        "video_id": video_id,
        "url": url,
        "transcript_status": status,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }, ensure_ascii=False), encoding="utf-8")
    return status
