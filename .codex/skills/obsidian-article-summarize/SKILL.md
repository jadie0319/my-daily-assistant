---
name: obsidian-article-summarize
description: Create an Obsidian note by summarizing a technical article URL with progress tracking, image download, and env.config paths (OBSIDIAN_VAULT, ARTICLE_DIR, ATTACHMENT_DIR).
---

# Obsidian Article Summarize

Use this skill when the user wants Claude `/obsidian:summarize-article` behavior in Codex.

## Inputs
- Optional language prefix: `kr` or `en` (default: `kr`)
- One technical article URL (`http://` or `https://`)

## Commands
- Background mode (default):
  - `./.codex/bin/summarize-article kr "https://example.com/post"`
- Synchronous mode:
  - `./.codex/bin/summarize-article --sync en "https://example.com/post"`
- Progress monitoring:
  - `./.codex/bin/article-progress`

## Workflow
1. Read `env.config` from repo root.
2. Extract title/author/content/images from article URL.
3. Create a progress file in `.codex/article-progress/`.
4. Generate Korean/English translation summary through `codex exec`.
5. Save note to `{OBSIDIAN_VAULT}{ARTICLE_DIR}/YYYY-MM-DD {title} (codex).md`.
6. Download article images to `{OBSIDIAN_VAULT}{ATTACHMENT_DIR}/` and append image embeds to the note.
7. Update progress JSON to `completed` or `failed`.

## Dependencies
- `python3`
- `codex` CLI
- outbound internet access for article/image download
