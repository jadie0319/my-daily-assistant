# Repository Guidelines

## IMPORTANT: Directory Access Rules

**READ THIS FIRST**: See `DIRECTORY_RULES.md` for absolute rules on which directories can be modified by Claude Code vs Codex. These rules MUST be followed at all times.

## Project Structure & Module Organization
This repo focuses on Obsidian automation for YouTube and article summarization.

- `.codex/skills/obsidian-youtube-summarize/`: Codex skill and Python scripts.
- `.codex/skills/obsidian-article-summarize/`: Codex article summarization skill.
- `.codex/bin/`: command-like wrappers (`summarize-youtube`, `youtube-progress`, `summarize-article`, `article-progress`).
- `.codex/article-progress/`: background job status JSON/log files.
- `.claude/commands/obsidian/`: legacy Claude command references.
- `env.config`: local paths (`OBSIDIAN_VAULT`, `YOUTUBE_DIR`, `ARTICLE_DIR`, `ATTACHMENT_DIR`).

Keep new automation code inside `.codex/skills/<skill-name>/scripts/` and avoid committing generated progress/log artifacts.

## Build, Test, and Development Commands
There is no separate build step. Use these commands:

- `python3 -m pip install youtube-transcript-api`: transcript API dependency.
- `yt-dlp --version`: verify metadata extractor is installed.
- `export PATH="$PWD/.codex/bin:$PATH"`: optional, run wrappers without `./`.
- `./.codex/bin/summarize-youtube kr "<youtube_url>"`: start background summarize job.
- `./.codex/bin/summarize-youtube --sync en "<youtube_url>"`: run foreground.
- `./.codex/bin/youtube-progress`: show processing/completed/failed jobs.
- `./.codex/bin/summarize-article kr "<article_url>"`: start background article summarize job.
- `./.codex/bin/summarize-article --sync en "<article_url>"`: run article summarize in foreground.
- `./.codex/bin/article-progress`: show article job status.
- `python3 -m py_compile .codex/skills/obsidian-youtube-summarize/scripts/*.py`: syntax check.
- `python3 -m py_compile .codex/skills/obsidian-article-summarize/scripts/*.py`: syntax check.

## Codex Command Replacement
Claude slash commands are replaced by local wrappers in `.codex/bin/`.

- Main replacement: `summarize-youtube` (equivalent to `summarize_youtube.md` workflow).
- Engine: `.codex/skills/obsidian-youtube-summarize/scripts/summarize_youtube.py`.
- Output target: `{OBSIDIAN_VAULT}{YOUTUBE_DIR}/YYYY-MM-DD <title>.md`.
- Progress tracking: `.codex/article-progress/YYYYMMDD-HHMMSS-youtube-<id>.json`.
- Main replacement: `summarize-article` (equivalent to `summarize_article.md` workflow).
- Engine: `.codex/skills/obsidian-article-summarize/scripts/summarize_article.py`.
- Output target: `{OBSIDIAN_VAULT}{ARTICLE_DIR}/YYYY-MM-DD <title> (codex).md`.
- Attachments target: `{OBSIDIAN_VAULT}{ATTACHMENT_DIR}/`.
- Progress tracking: `.codex/article-progress/YYYYMMDD-HHMMSS-article-<slug>.json`.

## Coding Style & Naming Conventions
- Language: Python 3 and Markdown.
- Use 4-space indentation, no tabs.
- Use `snake_case` for Python names and lowercase-hyphen skill folders.
- Keep scripts single-purpose; return machine-readable JSON on failures where practical.

## Testing Guidelines
Automated tests are not set up yet. Minimum checks:

- Validate one real YouTube URL and one failure input.
- Validate one real article URL and one failure URL.
- Confirm progress transitions: `processing -> completed|failed`.
- Verify created note path and frontmatter fields in Obsidian output (`author`, `tool`, `source`).
- Include command/output evidence in PR notes.

## Commit & Pull Request Guidelines
Use Conventional Commits from current history (`feat:`, `fix:`, `docs:`).  
PRs should include change summary, related issue/task, commands run, and any `env.config` or dependency impacts.

## Security & Configuration Tips
Treat vault paths and personal data as sensitive. Do not commit secrets or machine-specific tokens. Keep local config in `env.config` and sanitize any copied logs before sharing.
