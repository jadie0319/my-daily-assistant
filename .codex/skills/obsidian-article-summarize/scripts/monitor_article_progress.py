#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[4]
PROGRESS_DIR = REPO_ROOT / ".codex" / "article-progress"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show article summarize progress files")
    parser.add_argument("--limit", type=int, default=20, help="max number of records")
    return parser.parse_args()


def load_records(limit: int) -> list[dict[str, object]]:
    if not PROGRESS_DIR.exists():
        return []
    records: list[dict[str, object]] = []
    files = sorted(PROGRESS_DIR.glob("*-article-*.json"), reverse=True)
    for path in files[: max(1, limit)]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        payload["_path"] = str(path)
        records.append(payload)
    return records


def format_record(payload: dict[str, object]) -> str:
    status = str(payload.get("status", "unknown"))
    source = str(payload.get("url", ""))
    output_file = payload.get("output_file")
    error = payload.get("error")
    path = str(payload.get("_path", ""))

    if status == "processing":
        return f"[processing] {source}\n  progress: {path}"
    if status == "completed":
        return f"[completed] {source}\n  output: {output_file}\n  progress: {path}"
    if status == "failed":
        return f"[failed] {source}\n  error: {error}\n  progress: {path}"
    return f"[{status}] {source}\n  progress: {path}"


def main() -> int:
    args = parse_args()
    records = load_records(args.limit)
    if not records:
        print(f"No article progress files found in {PROGRESS_DIR}")
        return 0
    for item in records:
        print(format_record(item))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
