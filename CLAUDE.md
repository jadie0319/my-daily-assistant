# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## IMPORTANT: Directory Access Rules

**READ THIS FIRST**: See `DIRECTORY_RULES.md` for absolute rules on which directories can be modified by Claude Code vs Codex. These rules MUST be followed at all times.

## Project Overview

A personal daily life assistant. Scripts handle tasks like summarizing URLs, YouTube transcripts, PDF files, and other daily utilities. Outputs (summaries, notes, etc.) are saved to an Obsidian vault.

## Configuration

All environment settings are stored in `env.config` at the project root. Read this file at the start of any task that interacts with the filesystem or external services.

- **`OBSIDIAN_VAULT`**: Path to the Obsidian vault where all output notes are written.
- **`ARTICLE_DIR`**: Subdirectory within the vault for article summaries.
- **`YOUTUBE_DIR`**: Subdirectory within the vault for YouTube summaries.
- **`ATTACHMENT_DIR`**: Subdirectory within the vault for downloaded images.

## Slash Commands (`.claude/commands/obsidian/`)

### `summarize-article`

Summarizes a technical document and saves it as an Obsidian note.

**Supported input modes:**
1. URL (`http://` or `https://`) → fetches with WebFetch
2. Local PDF (ends with `.pdf` or starts with `file://`) → reads with Read tool (10-page chunks)
3. Plain text → used directly

**Output filename format:** `YYYY-MM-DD {title}.md`
**Output path:** `{OBSIDIAN_VAULT}/{ARTICLE_DIR}/`

PDF mode specifics:
- Title is derived from the filename (strip path/extension, replace `-`/`_` with spaces)
- `source` in YAML frontmatter is set to the absolute file path
- Images are extracted from PDF using `extract_pdf_images.py` and embedded in the note

### `summarize-youtube`

Extracts transcript from a YouTube URL, translates/summarizes it, and saves as an Obsidian note.

**Output filename format:** `YYYY-MM-DD {title} (claude).md`
**Output path:** `{OBSIDIAN_VAULT}/{YOUTUBE_DIR}/`

Uses `get_youtube_transcript.py` (in the same directory) to extract metadata and transcript via `youtube-transcript-api` and `yt-dlp`.

## Dependencies

```bash
pip3 install youtube-transcript-api yt-dlp PyMuPDF
```

| Package | Version | Purpose |
|---------|---------|---------|
| `youtube-transcript-api` | >= 1.2.4 | YouTube subtitle extraction |
| `yt-dlp` | >= 2026.3.3 | Video metadata (title, channel) extraction |
| `PyMuPDF` | >= 1.24 | PDF 이미지 추출 |

The `youtube-transcript-api` uses instance-based `YouTubeTranscriptApi()` with `.fetch()` and `.to_raw_data()`.

## Architecture

- **`.claude/commands/obsidian/`**: Slash commands for Claude Code interactive workflows
- **`.claude/article-progress/`**: JSON progress files for background summarization tasks
- **`get_youtube_transcript.py`**: CLI script that extracts YouTube transcripts. Prefers Korean (`ko`), falls back to English (`en`).
