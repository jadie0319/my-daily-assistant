---
name: obsidian-vault
description: Codex working rules for navigating the Obsidian vault, including targeted search, wiki-link references, backlink lookup, and tag-based filtering.
---

# Obsidian Vault

Use this skill when the user asks Codex to search or organize the Obsidian vault.

## Required Variables
Read `env.config` from repo root and load:
- `OBSIDIAN_VAULT`
- `DAILY_NOTE_DIR`
- `INBOX_DIR`
- `NOTES_DIR`
- `LIBRARY_DIR`, `MOC_DIR`, `TAG_VOCAB`

## Search Strategy
1. Prefer targeted search over broad vault scans.
2. Ignore `.obsidian`, `archive`, binaries, and attachment-heavy directories unless explicitly needed.
3. Prefer `rg` patterns such as:
   - backlinks: `rg -n "\\[\\[Note Name(\\|.*)?\\]\\]" "<vault-root>"`
   - tags: `rg -n "#topic/engineering\\b" "<vault-root>"`
   - headings: `rg -n "^## " "<vault-root>"`
4. Load only the files needed to answer the question.

## Working Rules
1. Treat the vault as user content, not an implementation dump.
2. Keep edits minimal and preserve the existing note structure.
3. Tags must come from `{OBSIDIAN_VAULT}/95.Vault/태그 어휘.md` (roots `ai/ dev/ invest/ self/ productivity/ business/ source/`). The old `topic/… type/… status/…` scheme is retired.
4. Notes carry `origin: mine | library` (user-written vs imported/AI) and `related:` wikilinks filled by the vault's `inbox-link` skill — follow `related` before grepping.
5. Write only into `INBOX_DIR` and `ATTACHMENT_DIR`; `NOTES_DIR`, `LIBRARY_DIR`, `MOC_DIR` are read-only for skills. Prefer the Obsidian CLI (`obsidian search/read/links/backlinks`) when Obsidian is running. Full rules: `obsidian-note-rules.md`.
4. Use exact file paths when reporting results so the user can navigate quickly.

## Examples
- `TDD 노트를 참조하는 노트 찾아줘`
- `#project/active 태그가 있는 노트만 보여줘`
- `이번 주 Daily Note 에서 회의 관련 항목만 추려줘`
