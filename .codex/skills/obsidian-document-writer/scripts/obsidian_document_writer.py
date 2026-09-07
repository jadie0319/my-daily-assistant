#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import re
from html import escape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[4]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish an Obsidian note to Confluence")
    parser.add_argument("source", nargs="?", help="markdown path or page title")
    parser.add_argument("--title", help="page title override")
    parser.add_argument("--body", help="raw markdown body for direct publishing")
    parser.add_argument("--dry-run", action="store_true", help="print the request payload without publishing")
    return parser.parse_args()


def load_env_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def resolve_markdown_path(arg: str, env: dict[str, str]) -> Path:
    vault = Path(env["OBSIDIAN_VAULT"]).expanduser()
    inbox_dir = env.get("INBOX_DIR", "").lstrip("/")
    notes_dir = env.get("NOTES_DIR", "").lstrip("/")

    if arg.startswith("inbox/"):
        return (vault / inbox_dir / arg.removeprefix("inbox/")).resolve()
    if arg.startswith("notes/"):
        return (vault / notes_dir / arg.removeprefix("notes/")).resolve()
    return (vault / arg).resolve()


def strip_frontmatter(text: str) -> str:
    return re.sub(r"(?s)\A---\n.*?\n---\n?", "", text, count=1)


def clean_obsidian_markdown(text: str) -> str:
    text = strip_frontmatter(text)
    text = re.sub(r"!\[\[[^\]]+\]\]", "", text)
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"(?m)^#[A-Za-z0-9/_-]+\s*$", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def title_from_path(path: Path) -> str:
    title = re.sub(r"^\d{4}-\d{2}-\d{2}\s+", "", path.stem)
    title = re.sub(r"\s+", " ", title).strip()
    return title or "Untitled"


def parse_source(args: argparse.Namespace, env: dict[str, str]) -> tuple[str, str]:
    if args.body:
        if not args.title and not args.source:
            raise RuntimeError("A title or source title is required when --body is used")
        return args.title or args.source or "Untitled", args.body

    if args.source and args.source.endswith(".md"):
        path = resolve_markdown_path(args.source, env)
        if not path.exists():
            raise FileNotFoundError(f"markdown file not found: {path}")
        content = clean_obsidian_markdown(path.read_text(encoding="utf-8"))
        title = args.title or title_from_path(path)
        return title, content

    if args.source and args.title:
        return args.title, args.source
    if args.source:
        return args.source, ""

    raise RuntimeError("Provide a markdown path, or use --title with --body")


def apply_inline_markup(text: str) -> str:
    text = escape(text)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<em>\1</em>", text)
    return text


def markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    blocks: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            blocks.append(f"<pre><code>{escape(chr(10).join(code_lines))}</code></pre>")
            i += 1
            continue

        heading = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading:
            level = len(heading.group(1))
            text = apply_inline_markup(heading.group(2).strip())
            blocks.append(f"<h{level}>{text}</h{level}>")
            i += 1
            continue

        unordered = re.match(r"^[-*]\s+(.+)$", stripped)
        ordered = re.match(r"^\d+\.\s+(.+)$", stripped)
        if unordered or ordered:
            tag = "ul" if unordered else "ol"
            items: list[str] = []
            while i < len(lines):
                current = lines[i].strip()
                match = re.match(r"^[-*]\s+(.+)$", current) if tag == "ul" else re.match(r"^\d+\.\s+(.+)$", current)
                if not match:
                    break
                items.append(f"<li>{apply_inline_markup(match.group(1).strip())}</li>")
                i += 1
            blocks.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue

        paragraph: list[str] = [stripped]
        i += 1
        while i < len(lines) and lines[i].strip():
            paragraph.append(lines[i].strip())
            i += 1
        blocks.append(f"<p>{apply_inline_markup(' '.join(paragraph))}</p>")

    return "\n".join(blocks)


def build_payload(title: str, html: str, env: dict[str, str]) -> dict[str, object]:
    required = [
        "CONFLUENCE_SPACE_KEY",
        "CONFLUENCE_PARENT_PAGE_ID",
    ]
    missing = [key for key in required if not env.get(key)]
    if missing:
        raise RuntimeError(f"Missing env.config values: {', '.join(missing)}")

    return {
        "type": "page",
        "title": title,
        "space": {"key": env["CONFLUENCE_SPACE_KEY"]},
        "ancestors": [{"id": int(env["CONFLUENCE_PARENT_PAGE_ID"])}],
        "body": {
            "storage": {
                "value": html,
                "representation": "storage",
            }
        },
    }


def publish(payload: dict[str, object], env: dict[str, str]) -> dict[str, object]:
    base_url = env.get("CONFLUENCE_URL")
    username = env.get("CONFLUENCE_USERNAME")
    password = env.get("CONFLUENCE_PASSWORD")
    if not base_url or not username or not password:
        raise RuntimeError("Confluence credentials are missing from env.config")

    endpoint = urljoin(base_url.rstrip("/") + "/", "rest/api/content")
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"Confluence API error {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Confluence connection failed: {exc}") from exc

    return json.loads(body)


def main() -> int:
    args = parse_args()
    env = load_env_config(REPO_ROOT / "env.config")
    title, markdown = parse_source(args, env)
    html = markdown_to_html(markdown) if markdown else "<p></p>"
    payload = build_payload(title, html, env)

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    response = publish(payload, env)
    base_url = env["CONFLUENCE_URL"].rstrip("/")
    webui = str(response.get("_links", {}).get("webui") or "")
    page_url = urljoin(base_url + "/", webui.lstrip("/")) if webui else base_url
    print(f"Published page: {page_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
