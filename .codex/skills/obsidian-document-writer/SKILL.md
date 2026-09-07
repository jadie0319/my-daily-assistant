---
name: obsidian-document-writer
description: Publish an Obsidian markdown note or provided markdown body to Confluence using the Confluence REST API and `env.config` credentials.
---

# Obsidian Document Writer

Use this skill when the user wants to publish an Obsidian note to Confluence from Codex without relying on Claude Playwright flows.

## Inputs
- A markdown file path such as:
  - `inbox/file.md`
  - `notes/file.md`
  - `relative/path/file.md`
- Or:
  - `--title "Page Title" --body "markdown text"`

## Required Variables
Read `env.config` from repo root and load:
- `CONFLUENCE_URL`
- `CONFLUENCE_SPACE_KEY`
- `CONFLUENCE_PARENT_PAGE_ID`
- `CONFLUENCE_USERNAME`
- `CONFLUENCE_PASSWORD`
- `OBSIDIAN_VAULT`
- `INBOX_DIR`
- `NOTES_DIR`

## Commands
- Preview request payload:
  - `./.codex/bin/obsidian-document-writer inbox/example.md --dry-run`
- Publish a note:
  - `./.codex/bin/obsidian-document-writer inbox/example.md`
- Publish direct markdown:
  - `./.codex/bin/obsidian-document-writer --title "Page Title" --body "# Heading"`

## Workflow
1. Resolve the input markdown source.
2. Strip frontmatter and Obsidian-only syntax:
   - `![[image]]`
   - `[[wiki-links]]`
   - tag-only lines
3. Convert markdown into simple HTML suitable for Confluence storage format.
4. Create the page with the Confluence REST API under the configured parent page.

## Rules
1. This is a Codex-native replacement for the old Playwright-based workflow.
2. Do not depend on `.claude` prompts or browser tooling.
3. Use `--dry-run` first when the user wants validation before publishing.
