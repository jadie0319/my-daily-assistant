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
from urllib.parse import unquote, urlparse
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
    mode: str
    value: str


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
        raise ValueError("Usage: summarize_article.py [--sync] [kr|en] <article_url|article_text>")

    first = arguments[0].lower()
    if first in {"kr", "ko", "en"}:
        lang = "kr" if first in {"kr", "ko"} else "en"
        value = " ".join(arguments[1:]).strip()
    else:
        lang = "kr"
        value = " ".join(arguments).strip()

    if not value:
        raise ValueError("Article input is empty")

    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        mode = "url"
    elif is_pdf_input(value):
        mode = "pdf"
    else:
        mode = "text"
    return SummaryInput(lang=lang, mode=mode, value=value)


def is_pdf_input(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme == "file":
        return parsed.path.lower().endswith(".pdf")
    return value.lower().endswith(".pdf")


def slugify(value: str, fallback: str = "article") -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or fallback



def load_tag_vocab(vault: str) -> list[str]:
    """Allowed tags = backticked values in {vault}/95.Vault/태그 어휘.md (see obsidian-note-rules.md)."""
    try:
        text = (Path(vault) / "95.Vault" / "태그 어휘.md").read_text(encoding="utf-8")
    except OSError:
        return []
    tags = re.findall(r"^\| `([a-z0-9/\-]+)` \|", text, re.M)
    return sorted({t for t in tags if not t.endswith("/")})  # drop root rows like `ai/`



def normalize_tags_to_vocab(markdown: str, allowed: list[str]) -> str:
    """Deterministic backstop: replace tags outside the vocabulary with their nearest
    existing ancestor; keep originals once in tags_original; list dropped ones in a comment."""
    if not allowed:
        return markdown
    vocab = set(allowed)
    m = re.match(r"(?s)^---\n(.*?)\n---\n?", markdown)
    if not m:
        return markdown
    fm, body = m.group(1), markdown[m.end():]
    tb = re.search(r"^tags:\s*\n((?:[ \t]+-[ \t]+.*\n?)+)", fm, re.M)
    if not tb:
        return markdown
    tags = [x.strip().strip("\"'") for x in re.findall(r"-\s+(.*)", tb.group(1))]
    new, dropped = [], []
    for tag in tags:
        cand = tag if tag in vocab else None
        parts = tag.split("/")
        while cand is None and len(parts) > 1:
            parts = parts[:-1]
            if "/".join(parts) in vocab:
                cand = "/".join(parts)
        if cand is None:
            dropped.append(tag)
        elif cand not in new:
            new.append(cand)
    if new == tags:
        return markdown
    block = "tags:\n" + "".join(f"  - {x}\n" for x in new)
    if "tags_original:" not in fm:
        block += "tags_original:\n" + "".join(f"  - {x}\n" for x in tags)
    fm = fm[: tb.start()] + block + fm[tb.end():].lstrip("\n")
    if dropped:
        body = body.rstrip("\n") + "\n\n<!-- 태그 제안: " + ", ".join(dropped) + " (어휘표에 없어 제거됨) -->\n"
    return f"---\n{fm.rstrip()}\n---\n\n{body.lstrip(chr(10))}"



def write_raw_note(env_values: dict[str, str], *, title: str, source: str, created: str,
                   summary_title: str, text: str) -> str | None:
    """Karpathy-style raw layer: keep the untouched source text next to the summary.

    Writes {OBSIDIAN_VAULT}{RAW_DIR}/YYYY-MM-DD <title> (raw).md and returns its stem
    (for the summary's `raw:` back-reference), or None when there is no text.
    See obsidian-note-rules.md §2-1.
    """
    if not text or not text.strip():
        return None
    vault = env_values.get("OBSIDIAN_VAULT")
    raw_dir = env_values.get("RAW_DIR") or "/02.Zettelkasten/000_Raw"
    out_dir = (Path(vault).expanduser() / raw_dir.lstrip("/")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{datetime.now().strftime('%Y-%m-%d')} {clean_filename(title)} (raw)"
    frontmatter = (
        "---\n"
        "type: raw\n"
        "origin: library\n"
        f"source: {yaml_quote(source)}\n"
        f"summary: {yaml_quote('[[' + summary_title + ']]')}\n"
        f"created: {yaml_quote(created)}\n"
        "tool: codex\n"
        "---\n\n"
    )
    (out_dir / f"{stem}.md").write_text(frontmatter + text.rstrip() + "\n", encoding="utf-8")
    return stem


def clean_filename(value: str) -> str:
    cleaned = re.sub(r"\s*\|\s*", " - ", value)
    cleaned = re.sub(r"[\\/:*?\"<>#^]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:120].rstrip(" -") or "untitled"


def normalize_author(author: str | None) -> str:
    if not author:
        return ""
    text = re.sub(r"\s+", " ", author).strip()
    return text


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f"\"{escaped}\""


def write_progress(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def create_progress_file(user_input: SummaryInput) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if user_input.mode == "url":
        parsed = urlparse(user_input.value)
        key = slugify(f"{parsed.netloc}-{parsed.path}", fallback="article")[:48]
        return PROGRESS_DIR / f"{timestamp}-article-{key}.json"
    if user_input.mode == "pdf":
        pdf_path = resolve_pdf_path(user_input.value)
        key = slugify(pdf_path.stem, fallback="pdf")[:48]
        return PROGRESS_DIR / f"{timestamp}-pdf-{key}.json"
    key = slugify(user_input.value[:30], fallback="text")[:48]
    return PROGRESS_DIR / f"{timestamp}-article-text-{key}.json"


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


def warn_if_short_text(user_input: SummaryInput) -> None:
    if user_input.mode == "text" and len(user_input.value) < 200:
        print(
            "Warning: input text is shorter than 200 characters. "
            "If you meant to pass a URL, it must start with http:// or https://",
            file=sys.stderr,
        )


def derive_text_title(text: str) -> str:
    heading_match = re.search(r"(?m)^\s*#\s+(.+?)\s*$", text)
    if heading_match:
        return clean_filename(heading_match.group(1).strip())

    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return "Untitled Article"

    sentence_match = re.search(r"(.+?[.!?])(?:\s|$)", normalized)
    if sentence_match:
        candidate = sentence_match.group(1).strip()
    else:
        candidate = normalized[:80].strip()
    return clean_filename(candidate[:80])


def resolve_pdf_path(value: str) -> Path:
    parsed = urlparse(value)
    if parsed.scheme == "file":
        raw_path = unquote(parsed.path or "")
        if parsed.netloc:
            raw_path = f"//{parsed.netloc}{raw_path}"
        pdf_path = Path(raw_path)
    else:
        pdf_path = Path(value).expanduser()
    return pdf_path.resolve()


def derive_pdf_title(pdf_path: Path) -> str:
    return clean_filename(re.sub(r"[-_]+", " ", pdf_path.stem).strip())


def extract_pdf_content(pdf_path: Path) -> str:
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pdfplumber is required for PDF summarization") from exc

    chunks: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                chunks.append(text)

    content = "\n\n".join(chunks).strip()
    content = re.sub(r"\n{3,}", "\n\n", content)
    if len(content) < 100:
        raise RuntimeError("PDF content is too short or appears to be image-only")
    if len(content) > 120_000:
        content = content[:120_000] + "\n\n[...TRUNCATED FOR PROCESSING LIMIT...]"
    return content


def build_prompt(
    *,
    lang: str,
    article_file: Path,
    title: str,
    author: str,
    created: str,
    source: str,
    allowed_tags: list[str] | None = None,
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
  9) origin
- tags: choose 3 to 5 tags ONLY from this allowed vocabulary (lowercase, '/'-hierarchical), plus `source/article`. Never invent a tag; if nothing fits, use the closest parent tag and add an HTML comment `<!-- 태그 제안: ... -->` at the end of the body.
  Allowed: {', '.join(allowed_tags) if allowed_tags else '(vocabulary file not found: use ai/ dev/ invest/ self/ productivity/ business/ roots only)'}
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
- source: {source or "<empty>"}
- tool: codex
- origin: library

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
origin: "library"
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
        if user_input.mode == "url":
            article_data = run_article_extractor(user_input.value)
            title = str(article_data.get("title") or f"Article {urlparse(user_input.value).netloc}").strip()
            author = normalize_author(str(article_data.get("author") or ""))
            source = user_input.value
            content = str(article_data.get("content") or "")
            images = article_data.get("images") or []
            if not isinstance(images, list):
                images = []
        elif user_input.mode == "pdf":
            pdf_path = resolve_pdf_path(user_input.value)
            title = derive_pdf_title(pdf_path)
            author = ""
            source = str(pdf_path)
            content = extract_pdf_content(pdf_path)
            images = []
        else:
            title = derive_text_title(user_input.value)
            author = ""
            source = ""
            content = user_input.value
            images = []

        created = datetime.now().strftime("%Y-%m-%d %H:%M")
        output_path, output_rel = resolve_output_path(title, env_values)
        attachment_abs_dir: Path | None = None
        attachment_rel_dir = ""
        if user_input.mode == "url":
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
                source=source,
                allowed_tags=load_tag_vocab(vault),
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
                    "origin": "library",
                },
            )
            summary = normalize_tags_to_vocab(summary, load_tag_vocab(vault))
            raw_stem = write_raw_note(
                env_values, title=title, source=source, created=created,
                summary_title=output_path.stem, text=content,
            )
            if raw_stem:
                summary = ensure_frontmatter_properties(summary, {"raw": yaml_quote("[[" + raw_stem + "]]")})

            if user_input.mode == "url" and attachment_abs_dir is not None:
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
        "--mode",
        user_input.mode,
        "--input",
        user_input.value,
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
    parser.add_argument("--mode", choices=["url", "text", "pdf"], help=argparse.SUPPRESS)
    parser.add_argument("--input", dest="worker_input", help=argparse.SUPPRESS)
    parser.add_argument("--progress-file", help=argparse.SUPPRESS)
    parser.add_argument("arguments", nargs="*")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.worker:
        if not args.lang or not args.mode or not args.worker_input or not args.progress_file:
            print("missing worker arguments", file=sys.stderr)
            return 1
        return run_worker(
            SummaryInput(lang=args.lang, mode=args.mode, value=args.worker_input),
            Path(args.progress_file),
        )

    try:
        user_input = parse_user_input(args.arguments)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    warn_if_short_text(user_input)

    progress_file = create_progress_file(user_input)
    payload: dict[str, object] = {
        "type": "article",
        "mode": user_input.mode,
        "status": "processing",
        "started_at": now_iso(),
        "completed_at": None,
        "output_file": None,
        "error": None,
    }
    if user_input.mode == "url":
        payload["url"] = user_input.value
    elif user_input.mode == "pdf":
        payload["file"] = str(resolve_pdf_path(user_input.value))
    else:
        payload["input"] = "text"
        payload["text_preview"] = user_input.value[:80]
    write_progress(progress_file, payload)

    if args.sync:
        return run_worker(user_input, progress_file)

    pid = launch_background_worker(user_input, progress_file)
    print("Background job started")
    if user_input.mode == "url":
        print(f"- URL: {user_input.value}")
    elif user_input.mode == "pdf":
        print(f"- PDF: {resolve_pdf_path(user_input.value)}")
    else:
        print(f"- Input: text ({len(user_input.value)} chars)")
    print(f"- Progress: {progress_file}")
    print(f"- Log: {progress_file.with_suffix('.log')}")
    print(f"- PID: {pid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
