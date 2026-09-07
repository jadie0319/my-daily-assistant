---
name: learning-tracker
description: Extract learning signals from Codex session logs and update the target Daily Note with a compact TIL section.
---

# Learning Tracker

Use this skill when the user asks to summarize what they learned, create a TIL entry, or extract learning points from a Codex workday.

## Inputs
- Optional target date in `YYYY-MM-DD`
- If omitted, default to yesterday

## Required Variables
Read `env.config` from repo root and load:
- `OBSIDIAN_VAULT`
- `DAILY_NOTE_DIR`

## Data Sources
- `~/.codex/history.jsonl`
- `~/.codex/sessions/YYYY/MM/DD/*.jsonl`

## Commands
- Update the Daily Note:
  - `./.codex/bin/learning-tracker`
  - `./.codex/bin/learning-tracker 2026-04-17`
- Print only:
  - `./.codex/bin/learning-tracker --stdout 2026-04-17`

## Workflow
1. Resolve `TARGET_DATE` from the argument or default to yesterday.
2. Collect user prompts from `~/.codex/history.jsonl` for `TARGET_DATE`.
3. Collect session metadata and tool usage from `~/.codex/sessions/YYYY/MM/DD/`.
4. Ask `codex exec` to extract concise learning points only from that evidence.
5. Update `{OBSIDIAN_VAULT}{DAILY_NOTE_DIR}/{TARGET_DATE}.md` by upserting `## TIL - {TARGET_DATE}`.

## Output Shape
- `## TIL - YYYY-MM-DD`
- One short summary line
- `### Technical Tools`
- `### Concepts`
- `### Problem Solving`

## Rules
1. Respect `DIRECTORY_RULES.md`.
2. Do not depend on `.claude` session logs or `.claude` skills.
3. Prefer explicit tool and concept names over vague summaries.
4. If there is not enough evidence for a section, write `- None`.
