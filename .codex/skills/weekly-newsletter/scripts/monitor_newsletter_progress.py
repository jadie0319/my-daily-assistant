#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[4]
PROGRESS_DIR = REPO_ROOT / ".codex" / "newsletter-progress"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Show weekly newsletter progress files")
    parser.add_argument("--limit", type=int, default=20, help="max number of records")
    return parser.parse_args()


def load_records(limit: int) -> list[dict[str, object]]:
    if not PROGRESS_DIR.exists():
        return []
    records: list[dict[str, object]] = []
    files = sorted(PROGRESS_DIR.glob("*.json"), reverse=True)
    for path in files[: max(limit, 1)]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        payload["_path"] = str(path)
        records.append(payload)
    return records


def format_record(payload: dict[str, object]) -> str:
    week = str(payload.get("week", ""))
    status = str(payload.get("status", "unknown"))
    output_file = payload.get("output_file")
    log_file = payload.get("log_file")
    error = payload.get("error")
    path = str(payload.get("_path", ""))

    if status == "processing":
        return f"[processing] {week}\n  progress: {path}\n  log: {log_file}"
    if status == "completed":
        return f"[completed] {week}\n  output: {output_file}\n  progress: {path}"
    if status == "failed":
        return f"[failed] {week}\n  error: {error}\n  progress: {path}\n  log: {log_file}"
    return f"[{status}] {week}\n  progress: {path}"


def main() -> int:
    args = parse_args()
    records = load_records(args.limit)
    if not records:
        print(f"No progress files found in {PROGRESS_DIR}")
        return 0
    for payload in records:
        print(format_record(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
