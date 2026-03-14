#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[4]
PROGRESS_DIR = REPO_ROOT / ".codex" / "newsletter-progress"
MAX_DOCS = 10
MAX_CHARS_PER_FILE = 12000


@dataclass
class WeekWindow:
    week_label: str
    saturday: date
    friday: date


@dataclass
class SourceBundle:
    daily_notes: list[Path]
    documents: list[Path]


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an Obsidian weekly newsletter from local notes")
    parser.add_argument("week", nargs="?", help="target week in YYYY-WNN format")
    parser.add_argument("--sync", action="store_true", help="run in foreground")
    parser.add_argument("--progress-file", help=argparse.SUPPRESS)
    return parser.parse_args()


def current_week_label(today: date | None = None) -> str:
    current = today or date.today()
    iso = current.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def parse_week_window(raw_week: str | None) -> WeekWindow:
    week_label = raw_week or current_week_label()
    match = re.fullmatch(r"(\d{4})-W(\d{2})", week_label)
    if not match:
        raise ValueError("Week must be in YYYY-WNN format")

    year = int(match.group(1))
    week = int(match.group(2))
    try:
        iso_monday = date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO week: {week_label}") from exc

    saturday = iso_monday - timedelta(days=2)
    friday = saturday + timedelta(days=6)
    return WeekWindow(week_label=week_label, saturday=saturday, friday=friday)


def write_progress(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def make_progress_path(week_label: str) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_week = week_label.lower().replace(" ", "-")
    return PROGRESS_DIR / f"{timestamp}-newsletter-{safe_week}.json"


def create_background_job(week_label: str | None) -> int:
    progress_path = make_progress_path(week_label or current_week_label())
    log_path = progress_path.with_suffix(".log")
    command = [sys.executable, str(THIS_FILE), "--sync", "--progress-file", str(progress_path)]
    if week_label:
        command.append(week_label)

    payload = {
        "type": "weekly-newsletter",
        "status": "processing",
        "week": week_label or current_week_label(),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "log_file": str(log_path),
    }
    write_progress(progress_path, payload)

    with log_path.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
            start_new_session=True,
        )

    payload["pid"] = process.pid
    payload["updated_at"] = now_iso()
    write_progress(progress_path, payload)

    print(f"Started weekly newsletter job for {payload['week']}")
    print(f"Progress: {progress_path}")
    print(f"Log: {log_path}")
    return 0


def clean_dir(value: str) -> str:
    return value.strip().strip("\"'").rstrip("/")


def resolve_path(base: Path, config_value: str) -> Path:
    cleaned = clean_dir(config_value)
    if not cleaned:
        return base
    if cleaned.startswith("/"):
        return base / cleaned.lstrip("/")
    return base / cleaned


def load_required_paths(env: dict[str, str]) -> tuple[Path, Path, Path, Path, Path]:
    required = ["OBSIDIAN_VAULT", "DAILY_NOTE_DIR", "INBOX_DIR", "NOTES_DIR", "NEWSLETTER_DIR"]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise KeyError(f"Missing env.config values: {', '.join(missing)}")

    vault = Path(env["OBSIDIAN_VAULT"].strip().strip("\"'")).expanduser()
    daily_dir = resolve_path(vault, env["DAILY_NOTE_DIR"])
    inbox_dir = resolve_path(vault, env["INBOX_DIR"])
    notes_dir = resolve_path(vault, env["NOTES_DIR"])
    newsletter_dir = resolve_path(vault, env["NEWSLETTER_DIR"])
    return vault, daily_dir, inbox_dir, notes_dir, newsletter_dir


def collect_daily_notes(daily_dir: Path, window: WeekWindow) -> list[Path]:
    results: list[Path] = []
    current = window.saturday
    while current <= window.friday:
        candidate = daily_dir / f"{current.isoformat()}.md"
        if candidate.exists():
            results.append(candidate)
        current += timedelta(days=1)
    return results


def modified_in_window(path: Path, window: WeekWindow) -> bool:
    try:
        modified = datetime.fromtimestamp(path.stat().st_mtime).date()
    except OSError:
        return False
    return window.saturday <= modified <= window.friday


def collect_documents(root_dirs: list[Path], window: WeekWindow) -> list[Path]:
    seen: set[Path] = set()
    candidates: list[Path] = []

    for root in root_dirs:
        if not root.exists():
            continue
        for path in root.rglob("*.md"):
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            if modified_in_window(path, window):
                candidates.append(path)

    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    return candidates[:MAX_DOCS]


def read_trimmed_text(path: Path, limit: int = MAX_CHARS_PER_FILE) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n\n[Truncated]"


def relative_to_vault(path: Path, vault: Path) -> str:
    try:
        return str(path.relative_to(vault))
    except ValueError:
        return str(path)


def render_source_sections(paths: list[Path], vault: Path, heading: str) -> str:
    if not paths:
        return f"## {heading}\n- None\n"

    blocks: list[str] = [f"## {heading}"]
    for path in paths:
        body = read_trimmed_text(path)
        blocks.append(f"### FILE: {relative_to_vault(path, vault)}")
        blocks.append(body or "[Empty file]")
    return "\n\n".join(blocks)


def build_prompt(vault: Path, window: WeekWindow, sources: SourceBundle) -> str:
    source_text = "\n\n".join(
        [
            render_source_sections(sources.daily_notes, vault, "Daily Notes"),
            render_source_sections(sources.documents, vault, "Weekly Documents"),
        ]
    ).strip()

    return f"""
You are writing an external-facing weekly newsletter from a private Obsidian vault.

Use only the source material below. Do not invent facts. If a section has weak evidence, say so plainly.

Week rules:
- Newsletter week label: {window.week_label}
- Coverage window: {window.saturday.isoformat()} to {window.friday.isoformat()}
- This week is defined as Saturday through Friday.

Privacy filter:
- Exclude private schedules, internal-only execution details, customer names, partner names, secrets, and tactical TODO noise.
- Keep reusable technical, leadership, learning, and industry insights.

Output requirements:
- Return markdown only. No code fences.
- Start with valid Obsidian frontmatter.
- Output file title must be "Weekly Digest - {window.week_label}".
- Save-friendly, polished Korean prose.
- Use concrete dates where helpful.
- Keep claims tied to the provided notes.

Frontmatter fields and order:
1) id
2) aliases
3) tags
4) created
5) period
6) source

Frontmatter template:
---
id: "{window.week_label}-newsletter"
aliases:
  - "Weekly Digest - {window.week_label}"
tags:
  - newsletter
  - weekly-digest
created: "{date.today().isoformat()}"
period: "{window.saturday.isoformat()} ~ {window.friday.isoformat()}"
source: "codex"
---

Required body structure:
# Weekly Digest - {window.week_label}

> One short quote-like takeaway sentence drawn from the week's material.

## Overview
2 short paragraphs summarizing the week.

## Technical Trends
- Bullet points with source-backed insights.

## Leadership and Organization Insights
- Bullet points with source-backed insights.

## Weekly Highlights
- Bullet points with date or source note references when possible.

## Key Lessons
1. Numbered lessons grounded in the notes.

## Next Focus
- Practical follow-up areas implied by the notes.

## Related Notes
- Wiki-link style references such as [[path-or-note-name]] for the most relevant source notes.

Source material:
{source_text}
""".strip()


def run_codex_summary(prompt: str, output_file: Path) -> None:
    command = [
        "codex",
        "-a",
        "never",
        "exec",
        prompt,
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False, cwd=str(REPO_ROOT))
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "codex exec failed"
        raise RuntimeError(message)

    content = result.stdout.strip()
    if not content:
        raise RuntimeError("codex exec returned empty content")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(content + "\n", encoding="utf-8")


def build_fallback_newsletter(window: WeekWindow, sources: SourceBundle, output_file: Path) -> None:
    lines = [
        "---",
        f'id: "{window.week_label}-newsletter"',
        "aliases:",
        f'  - "Weekly Digest - {window.week_label}"',
        "tags:",
        "  - newsletter",
        "  - weekly-digest",
        f'created: "{date.today().isoformat()}"',
        f'period: "{window.saturday.isoformat()} ~ {window.friday.isoformat()}"',
        'source: "codex"',
        "---",
        "",
        f"# Weekly Digest - {window.week_label}",
        "",
        "> This week did not contain enough source material for a fuller newsletter.",
        "",
        "## Overview",
        "",
        "수집된 자료가 충분하지 않아 간단한 요약만 남깁니다.",
        "",
        "## Technical Trends",
        "",
        "- No qualifying technical documents found for this week.",
        "",
        "## Leadership and Organization Insights",
        "",
        "- No qualifying leadership notes found for this week.",
        "",
        "## Weekly Highlights",
        "",
        f"- Daily Notes: {len(sources.daily_notes)} files",
        f"- Weekly Documents: {len(sources.documents)} files",
        "",
        "## Key Lessons",
        "",
        "1. Capture more explicit weekly learnings in source notes.",
        "",
        "## Next Focus",
        "",
        "- Add more reusable takeaways to daily and evergreen notes.",
        "",
        "## Related Notes",
        "",
        "- None",
    ]
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_sync(progress_file: str | None, week_label: str | None) -> int:
    progress_path = Path(progress_file) if progress_file else make_progress_path(week_label or current_week_label())
    window = parse_week_window(week_label)
    output_file: Path | None = None

    payload: dict[str, object] = {
        "type": "weekly-newsletter",
        "status": "processing",
        "week": window.week_label,
        "period": f"{window.saturday.isoformat()} ~ {window.friday.isoformat()}",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    write_progress(progress_path, payload)

    try:
        env = load_env_config(REPO_ROOT / "env.config")
        vault, daily_dir, inbox_dir, notes_dir, newsletter_dir = load_required_paths(env)
        output_file = newsletter_dir / f"{window.week_label}-newsletter.md"

        sources = SourceBundle(
            daily_notes=collect_daily_notes(daily_dir, window),
            documents=collect_documents([inbox_dir, notes_dir], window),
        )

        payload["daily_notes"] = [str(path) for path in sources.daily_notes]
        payload["documents"] = [str(path) for path in sources.documents]
        payload["output_file"] = str(output_file)
        payload["updated_at"] = now_iso()
        write_progress(progress_path, payload)

        if not sources.daily_notes and not sources.documents:
            build_fallback_newsletter(window, sources, output_file)
        else:
            prompt = build_prompt(vault, window, sources)
            run_codex_summary(prompt, output_file)

        payload["status"] = "completed"
        payload["updated_at"] = now_iso()
        write_progress(progress_path, payload)
        print(f"Created newsletter: {output_file}")
        return 0
    except Exception as exc:
        payload["status"] = "failed"
        payload["updated_at"] = now_iso()
        payload["error"] = str(exc)
        if output_file is not None:
            payload["output_file"] = str(output_file)
        write_progress(progress_path, payload)
        print(str(exc), file=sys.stderr)
        return 1


def main() -> int:
    args = parse_args()
    if args.sync:
        return run_sync(args.progress_file, args.week)
    return create_background_job(args.week)


if __name__ == "__main__":
    raise SystemExit(main())
