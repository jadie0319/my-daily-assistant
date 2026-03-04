---
name: obsidian-youtube-summarize
description: Create an Obsidian note by summarizing a YouTube URL or transcript with progress tracking, using env.config (OBSIDIAN_VAULT, YOUTUBE_DIR) and codex exec.
---

# Obsidian YouTube Summarize

Use this skill when the user wants Claude `/obsidian:summarize-youtube` behavior in Codex.

## Inputs
- Optional language prefix: `kr` or `en` (default: `kr`)
- Then either:
  - a YouTube URL (`youtube.com/watch?v=...` or `youtu.be/...`)
  - plain transcript text

## Commands
- Background mode (default):
  - `./.codex/bin/summarize-youtube kr "https://www.youtube.com/watch?v=VIDEO_ID"`
- Synchronous mode:
  - `./.codex/bin/summarize-youtube --sync en "https://www.youtube.com/watch?v=VIDEO_ID"`
- Progress monitoring:
  - `./.codex/bin/youtube-progress`

## Workflow
1. Read `env.config` from repo root.
2. If input is a YouTube URL, run `scripts/get_youtube_transcript.py` to fetch metadata and transcript.
3. Create a progress file in `.codex/article-progress/`.
4. Generate the summary through `codex exec` using translation/summarization constraints:
   - technical terms include original English on first mention,
   - sections: Highlights/Summary, Detailed Summary, Conclusion and Personal Views,
   - Obsidian YAML frontmatter with hierarchical tags.
5. Save to `{OBSIDIAN_VAULT}{YOUTUBE_DIR}/YYYY-MM-DD {title}.md`.
6. Update progress JSON to `completed` or `failed`.

## Dependencies
- `python3`
- `codex` CLI
- `youtube-transcript-api` (`python3 -m pip install youtube-transcript-api`)
- `yt-dlp` for title/channel extraction
