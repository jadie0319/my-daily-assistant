#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[4]
PROGRESS_DIR = REPO_ROOT / ".codex" / "article-progress"
TRANSCRIPT_SCRIPT = THIS_FILE.with_name("get_youtube_transcript.py")
DEFAULT_YOUTUBE_DIR = "/02.Zattelkasten/001_Inbox"


@dataclass
class SummaryInput:
    lang: str
    text: str


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def load_env_config(path: Path) -> dict[str, str]:
    if not path.exists():
        raise FileNotFoundError(f"env.config not found: {path}")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parse_user_input(arguments: list[str]) -> SummaryInput:
    if not arguments:
        raise ValueError("Usage: summarize_youtube.py [--sync] [kr|en] <youtube_url|transcript>")
    first = arguments[0].lower()
    if first in {"kr", "ko", "en"}:
        lang = "kr" if first in {"kr", "ko"} else "en"
        text = " ".join(arguments[1:]).strip()
    else:
        lang = "kr"
        text = " ".join(arguments).strip()
    if not text:
        raise ValueError("Input is empty after language parsing")
    return SummaryInput(lang=lang, text=text)


def is_youtube_url(text: str) -> bool:
    return ("youtube.com/watch?v=" in text) or ("youtu.be/" in text)


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


def slugify(value: str, fallback: str = "manual") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def clean_filename(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:120] or "untitled"


def channel_to_author(channel: str | None) -> str:
    if not channel:
        return "unknown"
    normalized = re.sub(r"\s+", " ", channel).strip()
    return normalized or "unknown"


def make_manual_title(text: str) -> str:
    words = re.sub(r"\s+", " ", text).strip().split(" ")
    title = " ".join(words[:8]).strip()
    if not title:
        return "Manual Transcript"
    return title[:100]


def write_progress(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_progress_file(input_text: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if is_youtube_url(input_text):
        key = extract_video_id(input_text) or "youtube"
    else:
        key = slugify(input_text[:40], fallback="manual")
    return PROGRESS_DIR / f"{timestamp}-youtube-{key}.json"


def run_transcript_extractor(url: str, lang: str) -> dict[str, str]:
    cmd = [sys.executable, str(TRANSCRIPT_SCRIPT), url, lang]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "transcript extraction failed"
        raise RuntimeError(message)
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid transcript JSON: {exc}") from exc
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    transcript = payload.get("transcript")
    if not transcript:
        raise RuntimeError("transcript is empty")
    return payload


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f"\"{escaped}\""


def build_prompt(
    *,
    lang: str,
    transcript_file: Path,
    title: str,
    author: str,
    created: str,
    source: str,
) -> str:
    output_language = "Korean" if lang == "kr" else "English"
    translation_rule = (
        "Translate to Korean. Keep important technical terms in English in parentheses on first mention."
        if lang == "kr"
        else "Write in English and keep technical terms precise."
    )
    return f"""
You are writing one Obsidian markdown note from a transcript.

Read transcript from this local file: {transcript_file}

Output constraints:
- Output markdown only. No code fences.
- Use this exact frontmatter field order:
  1) id
  2) aliases
  3) tags
  4) author
  5) created
  6) related
  7) source
  8) tool
- Keep tags hierarchical with '/' separators, lowercase, no spaces, max 6 tags.
- If uncertain, mark it explicitly in the body.
- Include code examples or pseudocode if they are present in the transcript.

Language and style:
- Final language: {output_language}
- {translation_rule}
- Use professional engineering terminology.

Required body structure:
1) Highlights/Summary: 2-3 paragraphs.
2) Detailed Summary: split by about 5-minute sections when timestamps are available; 2-3 paragraphs per section.
3) Conclusion and Personal Views: 5-10 bullet statements.

Use this metadata exactly:
- id: {title}
- author: {author}
- created: {created}
- source: {source}
- tool: codex

Frontmatter template:
---
id: {yaml_quote(title)}
aliases: <translated title when useful, otherwise same as id>
tags:
  - <tag-1>
author: {yaml_quote(author)}
created: {yaml_quote(created)}
related: []
source: {yaml_quote(source)}
tool: "codex"
---

Now produce the final note.
""".strip()


def ensure_frontmatter_properties(markdown: str, properties: dict[str, str]) -> str:
    frontmatter_match = re.match(r"(?s)^---\n(.*?)\n---\n?", markdown)
    if not frontmatter_match:
        body = markdown.strip()
        frontmatter_lines = [f"{key}: {value}" for key, value in properties.items()]
        frontmatter = "\n".join(frontmatter_lines)
        return f"---\n{frontmatter}\n---\n\n{body}" if body else f"---\n{frontmatter}\n---"

    frontmatter = frontmatter_match.group(1)
    body = markdown[frontmatter_match.end() :].lstrip("\n")
    lines = frontmatter.splitlines()

    for key, value in properties.items():
        found = False
        key_pattern = rf"^{re.escape(key)}\s*:"
        for i, line in enumerate(lines):
            if re.match(key_pattern, line):
                lines[i] = f"{key}: {value}"
                found = True
                break
        if not found:
            lines.append(f"{key}: {value}")

    new_frontmatter = "\n".join(lines)
    return f"---\n{new_frontmatter}\n---\n\n{body}".rstrip()


def run_codex_summary(prompt: str, output_file: Path) -> None:
    cmd = [
        "codex",
        "-a",
        "never",
        "exec",
        "--sandbox",
        "workspace-write",
        "--skip-git-repo-check",
        "--cd",
        str(REPO_ROOT),
        "-o",
        str(output_file),
        "-",
    ]
    result = subprocess.run(
        cmd,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        message = stderr or stdout or "codex exec failed"
        raise RuntimeError(message)


def resolve_output_path(title: str, env_values: dict[str, str]) -> tuple[Path, str]:
    vault = env_values.get("OBSIDIAN_VAULT")
    if not vault:
        raise RuntimeError("OBSIDIAN_VAULT is missing in env.config")
    youtube_dir = env_values.get("YOUTUBE_DIR") or DEFAULT_YOUTUBE_DIR
    output_dir = (Path(vault).expanduser() / youtube_dir.lstrip("/")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_prefix} {clean_filename(title)} (codex).md"
    output_path = output_dir / filename
    output_rel = f"{youtube_dir.rstrip('/')}/{filename}"
    return output_path, output_rel


def run_worker(user_input: SummaryInput, progress_file: Path) -> int:
    progress_payload = json.loads(progress_file.read_text(encoding="utf-8"))
    try:
        env_values = load_env_config(REPO_ROOT / "env.config")

        if is_youtube_url(user_input.text):
            yt_data = run_transcript_extractor(user_input.text, user_input.lang)
            title = yt_data.get("title") or f"YouTube {yt_data.get('video_id', '')}".strip()
            author = channel_to_author(yt_data.get("channel"))
            source = user_input.text
            transcript = yt_data["transcript"]
        else:
            title = make_manual_title(user_input.text)
            author = "unknown"
            source = "manual-input"
            transcript = user_input.text

        created = datetime.now().strftime("%Y-%m-%d %H:%M")
        output_path, output_rel = resolve_output_path(title, env_values)

        with tempfile.TemporaryDirectory(
            prefix="codex-youtube-",
            dir=PROGRESS_DIR,
        ) as tmp_dir:
            tmp_root = Path(tmp_dir)
            transcript_file = tmp_root / "transcript.txt"
            transcript_file.write_text(transcript, encoding="utf-8")
            summary_file = tmp_root / "summary.md"
            prompt = build_prompt(
                lang=user_input.lang,
                transcript_file=transcript_file,
                title=title,
                author=author,
                created=created,
                source=source,
            )
            run_codex_summary(prompt, summary_file)
            summary = summary_file.read_text(encoding="utf-8").strip()
            summary = ensure_frontmatter_properties(
                summary,
                {
                    "id": yaml_quote(title),
                    "author": yaml_quote(author),
                    "tool": "codex",
                    "source": yaml_quote(source),
                },
            )
            if not summary:
                raise RuntimeError("codex returned empty summary")

        output_path.write_text(summary + "\n", encoding="utf-8")

        progress_payload["status"] = "completed"
        progress_payload["completed_at"] = now_iso()
        progress_payload["output_file"] = output_rel
        progress_payload["error"] = None
        write_progress(progress_file, progress_payload)
        return 0

    except Exception as exc:  # noqa: BLE001
        progress_payload["status"] = "failed"
        progress_payload["completed_at"] = now_iso()
        progress_payload["output_file"] = None
        progress_payload["error"] = str(exc)
        write_progress(progress_file, progress_payload)
        return 1


def launch_background_worker(user_input: SummaryInput, progress_file: Path) -> int:
    log_file = progress_file.with_suffix(".log")
    cmd = [
        sys.executable,
        str(THIS_FILE),
        "--worker",
        "--lang",
        user_input.lang,
        "--input",
        user_input.text,
        "--progress-file",
        str(progress_file),
    ]
    with log_file.open("a", encoding="utf-8") as stream:
        process = subprocess.Popen(  # noqa: S603
            cmd,
            cwd=REPO_ROOT,
            stdout=stream,
            stderr=stream,
            start_new_session=True,
        )
    return process.pid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Codex replacement for summarize_youtube command",
    )
    parser.add_argument("--sync", action="store_true", help="run in foreground")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--lang", choices=["kr", "en"], help=argparse.SUPPRESS)
    parser.add_argument("--input", dest="worker_input", help=argparse.SUPPRESS)
    parser.add_argument("--progress-file", help=argparse.SUPPRESS)
    parser.add_argument("arguments", nargs="*")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.worker:
        if not args.worker_input or not args.lang or not args.progress_file:
            print("missing worker arguments", file=sys.stderr)
            return 1
        progress_path = Path(args.progress_file)
        return run_worker(SummaryInput(lang=args.lang, text=args.worker_input), progress_path)

    try:
        user_input = parse_user_input(args.arguments)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    progress_file = create_progress_file(user_input.text)
    payload = {
        "url": user_input.text,
        "type": "youtube",
        "status": "processing",
        "started_at": now_iso(),
        "completed_at": None,
        "output_file": None,
        "error": None,
    }
    write_progress(progress_file, payload)

    if args.sync:
        return run_worker(user_input, progress_file)

    pid = launch_background_worker(user_input, progress_file)
    print("Background job started")
    print(f"- Input: {user_input.text}")
    print(f"- Progress: {progress_file}")
    print(f"- Log: {progress_file.with_suffix('.log')}")
    print(f"- PID: {pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
