---
name: obsidian-article-summarize
description: Create an Obsidian note by summarizing a technical article URL, plain text, or local PDF with progress tracking, image download, and env.config paths (OBSIDIAN_VAULT, ARTICLE_DIR, ATTACHMENT_DIR).
---

# Obsidian Article Summarize

Use this skill when the user wants Claude `/obsidian:summarize-article` behavior in Codex.

## Inputs
- Optional language prefix: `kr` or `en` (default: `kr`)
- Then either:
  - a technical article URL (`http://` or `https://`)
  - a local PDF path (`/path/to/file.pdf`, `./file.pdf`, or `file:///path/to/file.pdf`)
  - plain article text / markdown

## Commands
- Background mode (default):
  - `./.codex/bin/summarize-article kr "https://example.com/post"`
  - `./.codex/bin/summarize-article kr "./paper.pdf"`
  - `./.codex/bin/summarize-article kr "# Title\n\narticle text..."`
- Synchronous mode:
  - `./.codex/bin/summarize-article --sync en "https://example.com/post"`
  - `./.codex/bin/summarize-article --sync kr "file:///Users/me/paper.pdf"`
  - `./.codex/bin/summarize-article --sync kr "plain article text"`
- Progress monitoring:
  - `./.codex/bin/article-progress`

## Workflow
1. Read `env.config` from repo root.
2. Detect input mode:
   - `http://` or `https://` prefix => URL mode
   - `.pdf` suffix (case-insensitive) or `file://` => PDF mode
   - otherwise => text mode
3. If text mode input is under 200 chars, warn and continue.
4. Create a progress file in `.codex/article-progress/`.
5. URL mode:
   - extract title/author/content/images from article URL
   - generate Korean/English translation summary through `codex exec`
   - download article images to `{OBSIDIAN_VAULT}{ATTACHMENT_DIR}/` and append embeds
6. PDF mode:
   - resolve the local PDF path and extract text with `pdfplumber`
   - derive title from the PDF filename, set `author` to empty string
   - set `source` to the resolved absolute PDF path
   - skip image download
   - fail if the PDF content is too short / image-only
7. Text mode:
   - skip URL extraction and image download
   - derive title from the first Markdown `#` heading, otherwise from the first sentence
   - set `author` to empty string and `source` to empty string
   - generate Korean/English translation summary through `codex exec`
8. Save note to `{OBSIDIAN_VAULT}{ARTICLE_DIR}/YYYY-MM-DD {title} (codex).md`.
9. Update progress JSON to `completed` or `failed`.

## Dependencies
- `python3`
- `pdfplumber` for PDF input
- `codex` CLI
- outbound internet access for article/image download
