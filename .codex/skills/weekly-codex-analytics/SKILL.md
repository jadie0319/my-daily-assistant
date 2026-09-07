---
name: weekly-codex-analytics
description: Build a weekly Codex usage report from `~/.codex/sessions`, including project distribution, work types, Jira mentions, and daily activity.
---

# Weekly Codex Analytics

Use this skill when the user asks for weekly Codex usage analytics, session statistics, or a report comparable to the old Claude weekly analytics workflow.

## Inputs
- Optional target week in `YYYY-WNN`
- If omitted, default to the current ISO week

## Required Variables
Read `env.config` from repo root and load:
- `OBSIDIAN_VAULT`

## Data Source
- `~/.codex/sessions/YYYY/MM/DD/*.jsonl`

## Command
- `./.codex/bin/weekly-codex-analytics`
- `./.codex/bin/weekly-codex-analytics 2026-W16`
- `./.codex/bin/weekly-codex-analytics --stdout 2026-W16`

## Workflow
1. Resolve the Monday-to-Friday window for the target ISO week.
2. Parse Codex session logs in that window.
3. Aggregate:
   - total sessions
   - total work time
   - tool invocations
   - project distribution by `cwd`
   - heuristic work types
   - Jira issue mentions
   - daily activity
4. Compare the week against the previous ISO week.
5. Save the report to `{OBSIDIAN_VAULT}/analytics/codex-weekly/YYYY-WNN.md`.

## Rules
1. This is a Codex-native replacement. Do not inspect `.claude/projects`.
2. The report must clearly state that classifications are heuristic.
3. Prefer exact dates and week labels in the output.
