#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[4]
HISTORY_PATH = Path.home() / ".codex" / "history.jsonl"
SESSIONS_ROOT = Path.home() / ".codex" / "sessions"


@dataclass
class SessionEvidence:
    session_id: str
    cwd: str
    tool_counts: Counter[str]
    message_snippets: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract Codex learning notes into a Daily Note")
    parser.add_argument("target_date", nargs="?", help="target date in YYYY-MM-DD format")
    parser.add_argument("--stdout", action="store_true", help="print the generated TIL instead of updating a note")
    return parser.parse_args()


def parse_target_date(raw: str | None) -> date:
    if not raw:
        return date.today() - timedelta(days=1)
    return datetime.strptime(raw, "%Y-%m-%d").date()


def load_env_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def resolve_daily_note_path(env: dict[str, str], target_date: date) -> Path:
    vault = env.get("OBSIDIAN_VAULT")
    daily_dir = env.get("DAILY_NOTE_DIR")
    if not vault or not daily_dir:
        raise RuntimeError("env.config must define OBSIDIAN_VAULT and DAILY_NOTE_DIR")
    root = Path(vault).expanduser()
    return (root / daily_dir.lstrip("/") / f"{target_date.isoformat()}.md").resolve()


def same_local_day(ts: int, target_date: date) -> bool:
    return datetime.fromtimestamp(ts).date() == target_date


def collect_history_entries(target_date: date) -> list[str]:
    if not HISTORY_PATH.exists():
        return []

    results: list[str] = []
    for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = payload.get("ts")
        text = str(payload.get("text") or "").strip()
        if not isinstance(ts, int) or not text:
            continue
        if same_local_day(ts, target_date):
            results.append(text)
    return results


def collect_session_evidence(target_date: date) -> list[SessionEvidence]:
    session_dir = SESSIONS_ROOT / f"{target_date.year:04d}" / f"{target_date.month:02d}" / f"{target_date.day:02d}"
    if not session_dir.exists():
        return []

    sessions: list[SessionEvidence] = []
    for session_file in sorted(session_dir.glob("*.jsonl")):
        session_id = ""
        cwd = ""
        tool_counts: Counter[str] = Counter()
        message_snippets: list[str] = []

        for raw in session_file.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if entry.get("type") == "session_meta":
                payload = entry.get("payload", {})
                session_id = str(payload.get("id") or session_id)
                cwd = str(payload.get("cwd") or cwd)
                continue

            if entry.get("type") != "response_item":
                continue

            payload = entry.get("payload", {})
            payload_type = payload.get("type")

            if payload_type == "function_call":
                name = str(payload.get("name") or "").strip()
                if name:
                    tool_counts[name] += 1
                continue

            if payload_type != "message":
                continue

            for item in payload.get("content", []):
                text = str(item.get("text") or "").strip()
                if text:
                    message_snippets.append(compact_whitespace(text)[:240])

        sessions.append(
            SessionEvidence(
                session_id=session_id or session_file.stem,
                cwd=cwd,
                tool_counts=tool_counts,
                message_snippets=message_snippets[:8],
            )
        )
    return sessions


def compact_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_evidence_text(history_entries: list[str], sessions: list[SessionEvidence], target_date: date) -> str:
    lines = [f"TARGET_DATE: {target_date.isoformat()}", "", "## User Prompts"]
    if history_entries:
        for text in history_entries[:40]:
            lines.append(f"- {compact_whitespace(text)[:400]}")
    else:
        lines.append("- No prompt history found.")

    lines.extend(["", "## Session Tool Usage"])
    if sessions:
        for session in sessions:
            location = session.cwd or "unknown"
            counts = ", ".join(f"{name}={count}" for name, count in session.tool_counts.most_common(8)) or "none"
            lines.append(f"- session={session.session_id} cwd={location} tools={counts}")
            for snippet in session.message_snippets[:4]:
                lines.append(f"  snippet: {snippet}")
    else:
        lines.append("- No Codex sessions found.")

    return "\n".join(lines)


def collect_tool_bullets(history_entries: list[str], sessions: list[SessionEvidence]) -> list[str]:
    joined = " ".join(history_entries).lower()
    tool_usage: Counter[str] = Counter()
    for session in sessions:
        tool_usage.update(session.tool_counts)

    bullets: list[str] = []
    if "apply_patch" in tool_usage:
        bullets.append("- `apply_patch`: Codex 수동 편집은 patch 단위로 적용하는 방식이 더 안전하다는 점")
    if "exec_command" in tool_usage:
        bullets.append("- `exec_command`: 로컬 검증과 파일 탐색을 터미널 명령 중심으로 수행하는 흐름")
    if "rg" in joined or "ripgrep" in joined:
        bullets.append("- `rg`: 대규모 텍스트 검색에서 기본 검색 도구로 쓰는 패턴")
    if "confluence" in joined:
        bullets.append("- `Confluence API`: 브라우저 자동화 대신 REST API 방식으로 게시 기능을 대체할 수 있다는 점")
    if "obsidian" in joined:
        bullets.append("- `Obsidian vault`: 노트 자동화 기능을 Codex 전용 skill과 wrapper로 분리해 관리하는 구조")
    return bullets[:4]


def collect_concept_bullets(history_entries: list[str]) -> list[str]:
    joined = " ".join(history_entries).lower()
    bullets: list[str] = []
    if any(token in joined for token in ["skill", "스킬"]):
        bullets.append("- `skill` 구조: 대화 트리거용 문서와 실제 실행 스크립트를 분리하는 설계")
    if any(token in joined for token in ["port", "포팅", "복제", "분리"]):
        bullets.append("- Codex 복제 원칙: Claude 기능을 참조만 하고 런타임 의존 없이 별도 구현해야 한다는 점")
    if any(token in joined for token in ["analytics", "분석"]):
        bullets.append("- 세션 분석 개념: `history.jsonl`과 `sessions/*.jsonl`의 역할이 서로 다르다는 점")
    if any(token in joined for token in ["workflow", "progress", "백그라운드"]):
        bullets.append("- 자동화 workflow: skill, wrapper, script를 연결해 동일 작업을 반복 가능하게 만드는 방식")
    return bullets[:4]


def collect_problem_solving_bullets(history_entries: list[str], sessions: list[SessionEvidence]) -> list[str]:
    joined = " ".join(history_entries).lower()
    bullets: list[str] = []
    if any(token in joined for token in ["permission", "권한", "sandbox"]):
        bullets.append("- sandbox 제약: `.codex` 내부 파일 권한 변경과 vault 쓰기에는 별도 권한이 필요하다는 점")
    if any(token in joined for token in ["codex exec", "session"]):
        bullets.append("- nested Codex 실행은 세션 접근 권한 이슈를 만들 수 있어, 로그 기반 후처리가 더 안정적이라는 점")
    if any(token in joined for token in ["confluence", "playwright"]):
        bullets.append("- Playwright 의존 기능은 API 기반으로 바꾸면 Codex 환경에서도 독립적으로 유지 가능하다는 점")
    if sessions and not bullets:
        bullets.append("- 세션 로그 구조를 먼저 확인하고 그 형태에 맞춰 기능을 다시 설계해야 안정적이라는 점")
    return bullets[:4]


def build_learning_section(target_date: date, history_entries: list[str], sessions: list[SessionEvidence]) -> str:
    tool_bullets = collect_tool_bullets(history_entries, sessions) or ["- None"]
    concept_bullets = collect_concept_bullets(history_entries) or ["- None"]
    problem_bullets = collect_problem_solving_bullets(history_entries, sessions) or ["- None"]
    summary = f"> {target_date.isoformat()} 작업에서 나온 도구, 구조, 문제 해결 학습 포인트를 정리했다."

    return "\n".join(
        [
            f"## TIL - {target_date.isoformat()}",
            "",
            summary,
            "",
            "### Technical Tools",
            *tool_bullets,
            "",
            "### Concepts",
            *concept_bullets,
            "",
            "### Problem Solving",
            *problem_bullets,
        ]
    )


def create_empty_daily_note(path: Path, target_date: date) -> None:
    content = "\n".join(
        [
            "---",
            f'id: "{target_date.isoformat()}"',
            "aliases:",
            f'  - "{target_date.strftime("%B %d, %Y")}"',
            "tags:",
            "  - daily-notes",
            f"created: {target_date.isoformat()} 09:00",
            f"modified: {target_date.isoformat()} 09:00",
            "---",
            "",
            "## Company TODO",
            "",
            "### Today",
            "",
            "### Tomorrow",
            "",
            "## Private TODO",
            "",
            "### Today",
            "",
            "### Tomorrow",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def upsert_til_section(note_path: Path, target_date: date, section: str) -> None:
    if not note_path.exists():
        create_empty_daily_note(note_path, target_date)

    original = note_path.read_text(encoding="utf-8")
    block = section.strip() + "\n"
    pattern = re.compile(
        rf"(?ms)^## TIL - {re.escape(target_date.isoformat())}\n.*?(?=^## |\Z)"
    )

    if pattern.search(original):
        updated = pattern.sub(block + "\n", original, count=1)
    else:
        updated = original.rstrip() + "\n\n" + block

    note_path.write_text(updated.rstrip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    target_date = parse_target_date(args.target_date)
    env = load_env_config(REPO_ROOT / "env.config")
    note_path = resolve_daily_note_path(env, target_date)

    history_entries = collect_history_entries(target_date)
    sessions = collect_session_evidence(target_date)
    output = build_learning_section(target_date, history_entries, sessions)

    if args.stdout:
        print(output)
        return 0

    upsert_til_section(note_path, target_date, output)
    print(f"Updated learning notes: {note_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
