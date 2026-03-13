---
name: daily-work-logger
description: Analyze work artifacts for a target day, update the Daily Note, and carry Tomorrow items into the next day using TARGET_DATE/NEXT_DATE handling.
---

# Daily Work Logger

Use this skill when the user asks to organize yesterday's work, build a daily log, or update a Daily Note from recent activity.

## Inputs
- Optional target date in `YYYY-MM-DD`
- If omitted, default to yesterday

## Required Variables
Read `env.config` from repo root and load:
- `OBSIDIAN_VAULT`
- `DAILY_NOTE_DIR`
- `INBOX_DIR`
- `NOTES_DIR`

## Core Rules
1. Compute `TARGET_DATE` from the argument or default to yesterday.
2. Compute `NEXT_DATE` as the calendar day after `TARGET_DATE`.
3. Use `TARGET_DATE` and `NEXT_DATE` consistently in every prompt, search, and edit step.
4. Respect `DIRECTORY_RULES.md`:
   - do not read or depend on `.claude` skills or Claude session data
   - operate only with Codex-owned files and root/shared files

## Execution
- In Codex, invoke the skill by name:
  - `daily-work-logger`
  - `daily-work-logger 2026-03-12`
- With no date argument, interpret the request as `TARGET_DATE = yesterday`.

## Workflow
1. Resolve `DAILY_NOTE` as `{OBSIDIAN_VAULT}{DAILY_NOTE_DIR}/{TARGET_DATE}.md`.
2. Gather evidence for `TARGET_DATE` from:
   - vault markdown files under the configured note directories
   - Codex session/history data under `~/.codex/`
   - meeting notes matching `{TARGET_DATE}-*.md`
3. Summarize findings into Daily Note sections for work log, meetings, learning, and tool activity.
4. Read the `TARGET_DATE` Daily Note and extract Tomorrow items from:
   - `## Company TODO` > `### Tomorrow`
   - `## Private TODO` > `### Tomorrow`
5. If no Tomorrow items exist, stop the carry-over step.
6. If items exist:
   - open `{OBSIDIAN_VAULT}{DAILY_NOTE_DIR}/{NEXT_DATE}.md`
   - append company items into `## Company TODO` > `### Today`
   - append private items into `## Private TODO` > `### Today`
   - avoid duplicating identical checklist items already present in `NEXT_DATE`
7. Report how many Tomorrow items were carried from `TARGET_DATE` to `NEXT_DATE`.

## Prompting Notes
- Any subagent or parallel analysis prompt that refers to a date window must receive both `TARGET_DATE` and `NEXT_DATE`.
- Prefer exact date comparisons instead of ambiguous relative phrases.
- When describing the carry-over result, use concrete dates in the final message.

## Expected Outcome
- `TARGET_DATE` Daily Note contains a consolidated work summary.
- `NEXT_DATE` Daily Note receives carry-over Today items from the previous day's Tomorrow sections.
