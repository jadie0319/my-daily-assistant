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
from urllib.parse import urlparse
from urllib.request import Request, urlopen

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[4]
PROGRESS_DIR = REPO_ROOT / ".codex" / "article-progress"
EXTRACT_SCRIPT = THIS_FILE.with_name("extract_article.py")
DEFAULT_ARTICLE_DIR = "/02.Zattelkasten/001_Inbox"
DEFAULT_ATTACHMENT_DIR = "/99.Attachments"


@dataclass
class SummaryInput:
    lang: str
    url: str


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
        raise ValueError("Usage: summarize_article.py [--sync] [kr|en] <article_url>")

    first = arguments[0].lower()
    if first in {"kr", "ko", "en"}:
        lang = "kr" if first in {"kr", "ko"} else "en"
        url = " ".join(arguments[1:]).strip()
    else:
        lang = "kr"
        url = " ".join(arguments).strip()

    if not url:
        raise ValueError("Article URL is empty")

    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Article URL must start with http:// or https://")
    return SummaryInput(lang=lang, url=url)


def slugify(value: str, fallback: str = "article") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback


def clean_filename(value: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", " ", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:120] or "untitled"


def normalize_author(author: str | None) -> str:
    if not author:
        return "unknown"
    text = re.sub(r"\s+", " ", author).strip()
    return text or "unknown"


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f"\"{escaped}\""


def write_progress(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_progress_file(url: str) -> Path:
    parsed = urlparse(url)
    key = slugify(f"{parsed.netloc}-{parsed.path}", fallback="article")[:48]
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return PROGRESS_DIR / f"{timestamp}-article-{key}.json"


def run_article_extractor(url: str) -> dict[str, object]:
    result = subprocess.run(
        [sys.executable, str(EXTRACT_SCRIPT), url],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "article extraction failed"
        raise RuntimeError(message)
    try:
        payload = json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid article JSON: {exc}") from exc
    if payload.get("error"):
        raise RuntimeError(str(payload["error"]))
    if not payload.get("content"):
        raise RuntimeError("article content is empty")
    return payload


def build_prompt(
    *,
    lang: str,
    article_file: Path,
    title: str,
    author: str,
    created: str,
    source: str,
) -> str:
    output_language = "Korean" if lang == "kr" else "English"
    translation_rule = (
        "Translate the article into Korean and keep original English technical terms in parentheses on first mention."
        if lang == "kr"
        else "Write in English and preserve original technical terms accurately."
    )
    return f"""
You are a technical translator and software engineering writer.
Read article text from this local file: {article_file}

Output constraints:
- Output markdown only. No code fences.
- Do not add facts not present in the source text.
- Use this exact frontmatter field order:
  1) id
  2) aliases
  3) tags
  4) author
  5) tool
  6) created
  7) related
  8) source
- Keep tags hierarchical with '/' separators, lowercase, and max 6 tags.
- If uncertain, mark uncertain parts explicitly.
- Include code snippets/pseudocode from source when available.

Language and style:
- Final language: {output_language}
- {translation_rule}
- Use professional software engineering terminology.

Required body structure:
## 1. Highlights/Summary
2-3 paragraphs summarizing the full article.

## 2. Detailed Summary
Split by logical subtopics/subheadings, 2-3 paragraphs per section.

## 3. Conclusion and Personal View
5-10 bullet statements and why this article matters for practitioners.

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
tool: codex
created: {yaml_quote(created)}
related: []
source: {yaml_quote(source)}
---
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
    result = subprocess.run(cmd, input=prompt, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        stdout = result.stdout.strip()
        raise RuntimeError(stderr or stdout or "codex exec failed")


def resolve_output_path(title: str, env_values: dict[str, str]) -> tuple[Path, str]:
    vault = env_values.get("OBSIDIAN_VAULT")
    if not vault:
        raise RuntimeError("OBSIDIAN_VAULT is missing in env.config")
    article_dir = env_values.get("ARTICLE_DIR") or DEFAULT_ARTICLE_DIR
    output_dir = (Path(vault).expanduser() / article_dir.lstrip("/")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    date_prefix = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_prefix} {clean_filename(title)} (codex).md"
    output_path = output_dir / filename
    output_rel = f"{article_dir.rstrip('/')}/{filename}"
    return output_path, output_rel


def resolve_attachment_dir(env_values: dict[str, str]) -> tuple[Path, str]:
    vault = env_values.get("OBSIDIAN_VAULT")
    if not vault:
        raise RuntimeError("OBSIDIAN_VAULT is missing in env.config")
    attachment_dir = env_values.get("ATTACHMENT_DIR") or DEFAULT_ATTACHMENT_DIR
    abs_dir = (Path(vault).expanduser() / attachment_dir.lstrip("/")).resolve()
    abs_dir.mkdir(parents=True, exist_ok=True)
    rel_dir = attachment_dir.lstrip("/")
    return abs_dir, rel_dir


def infer_ext(path: str) -> str:
    lower = path.lower()
    for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp"]:
        if lower.endswith(ext):
            return ext
    return ".img"


def build_attachment_name(index: int, image_url: str) -> str:
    parsed = urlparse(image_url)
    stem = Path(parsed.path).stem or f"image-{index:02d}"
    ext = infer_ext(parsed.path)
    safe_stem = slugify(stem, fallback=f"image-{index:02d}")[:50]
    return f"article-{index:02d}-{safe_stem}{ext}"


def download_one(url: str, dest: Path) -> None:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0 Safari/537.36"
            ),
        },
    )
    with urlopen(req, timeout=45) as response:  # noqa: S310
        data = response.read()
    dest.write_bytes(data)


def download_images(
    images: list[dict[str, str]],
    attachment_abs_dir: Path,
    attachment_rel_dir: str,
) -> tuple[list[str], list[str]]:
    embeds: list[str] = []
    failures: list[str] = []

    for idx, item in enumerate(images, 1):
        src = str(item.get("src", "")).strip()
        if not src:
            continue
        filename = build_attachment_name(idx, src)
        target = attachment_abs_dir / filename
        try:
            download_one(src, target)
            embeds.append(f"{attachment_rel_dir}/{filename}")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{src} ({exc})")
    return embeds, failures


def append_image_section(markdown: str, embeds: list[str], failures: list[str]) -> str:
    lines: list[str] = []
    if embeds:
        lines.append("## Images")
        for rel_path in embeds:
            lines.append(f"![[{rel_path}]]")
    if failures:
        lines.append("## Image Download Failures")
        for failure in failures:
            lines.append(f"- {failure}")

    if not lines:
        return markdown
    return markdown.rstrip() + "\n\n" + "\n".join(lines) + "\n"


def run_worker(user_input: SummaryInput, progress_file: Path) -> int:
    progress_payload = json.loads(progress_file.read_text(encoding="utf-8"))
    try:
        env_values = load_env_config(REPO_ROOT / "env.config")
        article_data = run_article_extractor(user_input.url)

        title = str(article_data.get("title") or f"Article {urlparse(user_input.url).netloc}").strip()
        author = normalize_author(str(article_data.get("author") or ""))
        content = str(article_data.get("content") or "")
        images = article_data.get("images") or []
        if not isinstance(images, list):
            images = []

        created = datetime.now().strftime("%Y-%m-%d %H:%M")
        output_path, output_rel = resolve_output_path(title, env_values)
        attachment_abs_dir, attachment_rel_dir = resolve_attachment_dir(env_values)

        with tempfile.TemporaryDirectory(prefix="codex-article-", dir=PROGRESS_DIR) as tmp_dir:
            tmp_root = Path(tmp_dir)
            content_file = tmp_root / "article.txt"
            content_file.write_text(content, encoding="utf-8")
            summary_file = tmp_root / "summary.md"

            prompt = build_prompt(
                lang=user_input.lang,
                article_file=content_file,
                title=title,
                author=author,
                created=created,
                source=user_input.url,
            )
            run_codex_summary(prompt, summary_file)

            summary = summary_file.read_text(encoding="utf-8").strip()
            summary = ensure_frontmatter_properties(
                summary,
                {
                    "id": yaml_quote(title),
                    "author": yaml_quote(author),
                    "tool": "codex",
                    "source": yaml_quote(user_input.url),
                },
            )

            image_embeds, image_failures = download_images(images, attachment_abs_dir, attachment_rel_dir)
            summary = append_image_section(summary, image_embeds, image_failures)

        output_path.write_text(summary.rstrip() + "\n", encoding="utf-8")

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
        "--url",
        user_input.url,
        "--progress-file",
        str(progress_file),
    ]
    with log_file.open("a", encoding="utf-8") as stream:
        proc = subprocess.Popen(  # noqa: S603
            cmd,
            cwd=REPO_ROOT,
            stdout=stream,
            stderr=stream,
            start_new_session=True,
        )
    return proc.pid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codex replacement for summarize_article command")
    parser.add_argument("--sync", action="store_true", help="run in foreground")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--lang", choices=["kr", "en"], help=argparse.SUPPRESS)
    parser.add_argument("--url", dest="worker_url", help=argparse.SUPPRESS)
    parser.add_argument("--progress-file", help=argparse.SUPPRESS)
    parser.add_argument("arguments", nargs="*")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.worker:
        if not args.lang or not args.worker_url or not args.progress_file:
            print("missing worker arguments", file=sys.stderr)
            return 1
        return run_worker(SummaryInput(lang=args.lang, url=args.worker_url), Path(args.progress_file))

    try:
        user_input = parse_user_input(args.arguments)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    progress_file = create_progress_file(user_input.url)
    payload = {
        "url": user_input.url,
        "type": "article",
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
    print(f"- Input: {user_input.url}")
    print(f"- Progress: {progress_file}")
    print(f"- Log: {progress_file.with_suffix('.log')}")
    print(f"- PID: {pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
