#!/usr/bin/env python3
"""Claude Code PostToolUse hook: after any Write/Edit that touches a note under the
vault's Inbox, run scripts/check_obsidian_note.py --fix --no-rename on it.

This is the deterministic layer of obsidian-note-rules.md: whatever the model
wrote (wrong tags, missing origin), the note is normalised right after the write,
including writes done later by image-embedding steps. Never blocks the tool
(always exits 0); prints a one-line result so the model sees what changed.
"""
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHECKER = os.path.join(REPO, "scripts", "check_obsidian_note.py")
INBOX_MARKER = "/02.Zettelkasten/001_Inbox/"


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    tool_input = payload.get("tool_input") or {}
    path = tool_input.get("file_path") or tool_input.get("path") or ""
    if not path.endswith(".md") or INBOX_MARKER not in path or not os.path.exists(path):
        return
    if not os.path.exists(CHECKER):
        print("[inbox-check] checker missing:", CHECKER)
        return
    res = subprocess.run(
        [sys.executable, CHECKER, path, "--fix", "--no-rename"],
        capture_output=True, text=True, timeout=60,
    )
    out = (res.stdout or "").strip().splitlines()
    summary = [ln for ln in out if ln.startswith(("RESULT", "  -"))]
    print("[inbox-check] " + os.path.basename(path) + " | " + " ".join(summary[-6:]))
    if res.returncode != 0 and "RESULT: OK" not in res.stdout:
        print("[inbox-check] violations remain — report them to the user; do not silently continue.")


if __name__ == "__main__":
    main()
