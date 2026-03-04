#!/usr/bin/env python3
import json
import re
import subprocess
import sys
import warnings

warnings.filterwarnings("ignore", category=UserWarning, module="urllib3")

try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    print(json.dumps({"error": "youtube_transcript_api is not installed"}))
    sys.exit(1)


def first_non_empty(*values: str | None) -> str | None:
    for value in values:
        if value and str(value).strip():
            return str(value).strip()
    return None


def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=|/)([0-9A-Za-z_-]{11}).*",
        r"(?:be/)([0-9A-Za-z_-]{11}).*",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_video_metadata(url: str) -> tuple[str | None, str | None]:
    # Primary path: parse yt-dlp JSON and use channel/uploader fallbacks.
    try:
        result = subprocess.run(
            ["yt-dlp", "-J", "--no-playlist", url],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            payload = json.loads(result.stdout)
            title = first_non_empty(
                payload.get("title"),
                payload.get("fulltitle"),
            )
            channel = first_non_empty(
                payload.get("channel"),
                payload.get("uploader"),
                payload.get("channel_id"),
                payload.get("uploader_id"),
            )
            return title, channel
    except (json.JSONDecodeError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback path: lightweight print extraction.
    try:
        result = subprocess.run(
            ["yt-dlp", "--print", "%(title)s\n%(channel)s\n%(uploader)s", "--no-playlist", url],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if result.returncode == 0:
            lines = [line.strip() for line in result.stdout.splitlines()]
            title = first_non_empty(lines[0] if len(lines) > 0 else None)
            channel = first_non_empty(
                lines[1] if len(lines) > 1 else None,
                lines[2] if len(lines) > 2 else None,
            )
            return title, channel
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None, None


def get_transcript(video_id: str, lang: str) -> tuple[str | None, str | None]:
    language_map = {"kr": ["ko", "en"], "en": ["en", "ko"]}
    languages = language_map.get(lang, ["ko", "en"])
    try:
        api = YouTubeTranscriptApi()
        transcript_data = api.fetch(video_id, languages=languages).to_raw_data()
        merged = " ".join(item["text"] for item in transcript_data)
        return merged, None
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python3 get_youtube_transcript.py <url> [kr|en]"}))
        return 1

    url = sys.argv[1]
    lang = sys.argv[2] if len(sys.argv) > 2 else "kr"

    video_id = extract_video_id(url)
    if not video_id:
        print(json.dumps({"error": "Invalid YouTube URL"}))
        return 1

    title, channel = get_video_metadata(url)
    transcript, error = get_transcript(video_id, lang)
    if error:
        print(json.dumps({"error": error}))
        return 1

    result = {
        "title": title,
        "channel": channel,
        "video_id": video_id,
        "transcript": transcript,
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
