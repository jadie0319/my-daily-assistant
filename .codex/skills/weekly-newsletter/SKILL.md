---
name: weekly-newsletter
description: Create an external-facing weekly newsletter from Obsidian notes for a Saturday-to-Friday week using env.config paths and Codex-only files. Use when the user asks for "weekly newsletter", "뉴스레터 만들어줘", "이번 주 글 정리", or `weekly-newsletter`.
---

# Weekly Newsletter

Use this skill when the user wants the Claude `weekly-newsletter` workflow in Codex, without depending on `.claude` files at runtime.

## Inputs
- Optional target week in `YYYY-WNN`
- If omitted, use the current ISO week and interpret it as this skill's Saturday-to-Friday newsletter window

## Required Variables
Read `env.config` from repo root and load:
- `OBSIDIAN_VAULT`
- `DAILY_NOTE_DIR`
- `INBOX_DIR`
- `NOTES_DIR`
- `NEWSLETTER_DIR`

## Core Rules
1. Respect `DIRECTORY_RULES.md`.
2. Do not modify or execute anything under `.claude/`.
3. Use only `.codex` scripts plus shared root files such as `env.config`.
4. Treat the newsletter week as Saturday through Friday.
5. Filter out internal-only details, private TODOs, personal schedules, and customer or partner specifics.

## Commands
- Background mode:
  - `./.codex/bin/weekly-newsletter`
  - `./.codex/bin/weekly-newsletter 2026-W03`
- Synchronous mode:
  - `./.codex/bin/weekly-newsletter --sync`
  - `./.codex/bin/weekly-newsletter --sync 2026-W03`
- Progress monitoring:
  - `./.codex/bin/newsletter-progress`

## Workflow
1. Resolve the target week and convert it to:
   - `SATURDAY`
   - `FRIDAY`
   - `WEEK_NUM`
2. Gather Daily Notes from `{OBSIDIAN_VAULT}{DAILY_NOTE_DIR}/YYYY-MM-DD.md` for each day in the window.
3. Gather candidate markdown documents modified during the same window under:
   - `{OBSIDIAN_VAULT}{INBOX_DIR}`
   - `{OBSIDIAN_VAULT}{NOTES_DIR}`
4. Build a bounded source bundle from those notes and documents.
5. Run `codex exec` to draft the newsletter in markdown with Obsidian frontmatter.
6. Save the output to `{OBSIDIAN_VAULT}{NEWSLETTER_DIR}/{WEEK_NUM}-newsletter.md`.
7. Update the progress JSON to `completed` or `failed`.

## Expected Output
- Obsidian note path: `{OBSIDIAN_VAULT}{NEWSLETTER_DIR}/YYYY-WNN-newsletter.md`
- Progress file path: `.codex/newsletter-progress/*.json`

## Prompting Notes
- Use concrete dates in prompts and final output.
- Prefer source-backed statements only.
- If no source files exist for a section, say so explicitly instead of inventing content.
