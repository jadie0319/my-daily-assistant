#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parents[4]
SESSIONS_ROOT = Path.home() / ".codex" / "sessions"
DEFAULT_OUTPUT_DIR = "analytics/codex-weekly"
JIRA_EXCLUDE_PREFIXES = {"UTF", "GPT", "HTTP", "HTTPS", "JSON", "YAML"}


@dataclass
class WeekWindow:
    week_label: str
    monday: date
    friday: date


@dataclass
class SessionStats:
    session_id: str
    cwd: str
    started_at: datetime | None
    ended_at: datetime | None
    active_minutes: int
    prompts: list[str]
    tool_counts: Counter[str]
    jira_issues: set[str]

    @property
    def duration_minutes(self) -> int:
        return self.active_minutes

    @property
    def project_name(self) -> str:
        cwd = self.cwd.strip()
        if not cwd:
            return "unknown"
        parts = Path(cwd).parts
        return parts[-1] if parts else cwd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a weekly Codex usage analytics note")
    parser.add_argument("week", nargs="?", help="target week in YYYY-WNN format")
    parser.add_argument("--stdout", action="store_true", help="print the report instead of writing it to the vault")
    return parser.parse_args()


def load_env_config(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        clean = line.strip()
        if not clean or clean.startswith("#") or "=" not in clean:
            continue
        key, value = clean.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def current_week_label(today: date | None = None) -> str:
    current = today or date.today()
    iso = current.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def parse_week_window(raw_week: str | None) -> WeekWindow:
    week_label = raw_week or current_week_label()
    match = re.fullmatch(r"(\d{4})-W(\d{2})", week_label)
    if not match:
        raise ValueError("Week must be in YYYY-WNN format")

    year = int(match.group(1))
    week = int(match.group(2))
    monday = date.fromisocalendar(year, week, 1)
    friday = monday + timedelta(days=4)
    return WeekWindow(week_label=week_label, monday=monday, friday=friday)


def resolve_output_path(env: dict[str, str], week_label: str) -> Path:
    vault = env.get("OBSIDIAN_VAULT")
    if not vault:
        raise RuntimeError("env.config must define OBSIDIAN_VAULT")
    output_dir = Path(vault).expanduser() / DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"{week_label}.md"


def iter_session_files(window: WeekWindow) -> list[Path]:
    files: list[Path] = []
    current = window.monday
    while current <= window.friday:
        session_dir = SESSIONS_ROOT / f"{current.year:04d}" / f"{current.month:02d}" / f"{current.day:02d}"
        if session_dir.exists():
            files.extend(sorted(session_dir.glob("*.jsonl")))
        current += timedelta(days=1)
    return files


def extract_texts_from_message(payload: dict[str, object]) -> list[str]:
    texts: list[str] = []
    for item in payload.get("content", []):
        text = str(item.get("text") or "").strip()
        if text:
            texts.append(re.sub(r"\s+", " ", text))
    return texts


def extract_jira_issues(text: str) -> set[str]:
    matches = set(re.findall(r"\b[A-Z]{2,10}-\d+\b", text))
    return {item for item in matches if item.split("-", 1)[0] not in JIRA_EXCLUDE_PREFIXES}


def parse_session(path: Path) -> SessionStats:
    session_id = path.stem
    cwd = ""
    timestamps: list[datetime] = []
    active_turn_start: datetime | None = None
    active_minutes = 0
    prompts: list[str] = []
    tool_counts: Counter[str] = Counter()
    jira_issues: set[str] = set()

    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        raw_ts = entry.get("timestamp")
        if isinstance(raw_ts, str):
            try:
                timestamps.append(datetime.fromisoformat(raw_ts.replace("Z", "+00:00")))
            except ValueError:
                pass

        if entry.get("type") == "session_meta":
            payload = entry.get("payload", {})
            session_id = str(payload.get("id") or session_id)
            cwd = str(payload.get("cwd") or cwd)
            continue

        if entry.get("type") == "event_msg":
            payload = entry.get("payload", {})
            payload_type = payload.get("type")
            if payload_type == "task_started" and raw_ts:
                try:
                    active_turn_start = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except ValueError:
                    active_turn_start = None
            elif payload_type == "task_complete" and active_turn_start and raw_ts:
                try:
                    completed_at = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                except ValueError:
                    completed_at = None
                if completed_at and completed_at >= active_turn_start:
                    delta = int((completed_at - active_turn_start).total_seconds() // 60)
                    active_minutes += max(1, min(delta, 180))
                active_turn_start = None
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

        role = payload.get("role")
        texts = extract_texts_from_message(payload)
        if role == "user":
            prompts.extend(texts)
            for text in texts:
                jira_issues.update(extract_jira_issues(text))

    started_at = min(timestamps) if timestamps else None
    ended_at = max(timestamps) if timestamps else None
    return SessionStats(
        session_id=session_id,
        cwd=cwd,
        started_at=started_at,
        ended_at=ended_at,
        active_minutes=active_minutes or max(1, min(len(prompts) * 8, 120)),
        prompts=prompts,
        tool_counts=tool_counts,
        jira_issues=jira_issues,
    )


def classify_session(session: SessionStats) -> str:
    text = " ".join(session.prompts).lower()
    if any(token in text for token in ["review", "검토", "버그", "bug", "fix", "이슈"]):
        return "bug-fix-review"
    if any(token in text for token in ["refactor", "리팩토링", "정리", "cleanup"]):
        return "refactoring"
    if any(token in text for token in ["문서", "docs", "readme", "guide", "정리해줘"]):
        return "documentation"
    if any(token in text for token in ["test", "테스트"]):
        return "testing"
    if session.tool_counts.get("apply_patch", 0) or session.tool_counts.get("exec_command", 0) > 3:
        return "implementation"
    return "analysis"


def aggregate(window: WeekWindow) -> dict[str, object]:
    sessions = [parse_session(path) for path in iter_session_files(window)]
    project_totals: dict[str, dict[str, int]] = defaultdict(lambda: {"sessions": 0, "minutes": 0})
    type_totals: Counter[str] = Counter()
    day_totals: dict[str, dict[str, int]] = defaultdict(lambda: {"sessions": 0, "minutes": 0})
    jira_totals: dict[str, dict[str, int]] = defaultdict(lambda: {"sessions": 0, "minutes": 0})

    total_minutes = 0
    total_tool_calls = 0

    for session in sessions:
        minutes = session.duration_minutes
        project = session.project_name
        work_type = classify_session(session)
        session_day = (session.started_at.date() if session.started_at else window.monday).isoformat()

        total_minutes += minutes
        total_tool_calls += sum(session.tool_counts.values())
        project_totals[project]["sessions"] += 1
        project_totals[project]["minutes"] += minutes
        type_totals[work_type] += 1
        day_totals[session_day]["sessions"] += 1
        day_totals[session_day]["minutes"] += minutes

        for issue in session.jira_issues:
            jira_totals[issue]["sessions"] += 1
            jira_totals[issue]["minutes"] += minutes

    return {
        "sessions": sessions,
        "total_sessions": len(sessions),
        "total_minutes": total_minutes,
        "total_tool_calls": total_tool_calls,
        "project_totals": dict(project_totals),
        "type_totals": type_totals,
        "day_totals": dict(day_totals),
        "jira_totals": dict(jira_totals),
    }


def format_minutes(value: int) -> str:
    hours, minutes = divmod(value, 60)
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def render_comparison(current: int, previous: int) -> str:
    if previous == 0:
        return "new"
    delta = current - previous
    ratio = (delta / previous) * 100
    return f"{ratio:+.0f}%"


def render_report(window: WeekWindow, current: dict[str, object], previous: dict[str, object]) -> str:
    project_lines = []
    project_totals = current["project_totals"]
    total_minutes = current["total_minutes"] or 1
    for project, stats in sorted(project_totals.items(), key=lambda item: item[1]["minutes"], reverse=True):
        ratio = (stats["minutes"] / total_minutes) * 100
        project_lines.append(
            f"| {project} | {stats['sessions']} | {format_minutes(stats['minutes'])} | {ratio:.0f}% |"
        )
    if not project_lines:
        project_lines.append("| none | 0 | 0m | 0% |")

    type_lines = []
    type_totals = current["type_totals"]
    for work_type, count in type_totals.most_common():
        ratio = (count / max(1, current["total_sessions"])) * 100
        type_lines.append(f"| {work_type} | {count} | {ratio:.0f}% |")
    if not type_lines:
        type_lines.append("| none | 0 | 0% |")

    jira_lines = []
    jira_totals = current["jira_totals"]
    for issue, stats in sorted(jira_totals.items(), key=lambda item: item[1]["sessions"], reverse=True):
        jira_lines.append(
            f"| [[{issue}]] | {stats['sessions']} | {format_minutes(stats['minutes'])} |"
        )
    if not jira_lines:
        jira_lines.append("| none | 0 | 0m |")

    day_lines = []
    for day_key in sorted(current["day_totals"]):
        stats = current["day_totals"][day_key]
        day_lines.append(f"| {day_key} | {stats['sessions']} | {format_minutes(stats['minutes'])} |")
    if not day_lines:
        day_lines.append("| none | 0 | 0m |")

    return "\n".join(
        [
            "---",
            f"created: {date.today().isoformat()}",
            "type: codex-analytics",
            "period: weekly",
            f"week: {window.week_label}",
            "tags:",
            "  - analytics/codex",
            "  - analytics/weekly",
            "---",
            "",
            f"# Codex Weekly Analytics - {window.week_label}",
            "",
            f"> Analysis period: {window.monday.isoformat()} to {window.friday.isoformat()}",
            "",
            "## Summary Statistics",
            "",
            "| Metric | This Week | Previous Week | Change |",
            "| --- | --- | --- | --- |",
            f"| Total sessions | {current['total_sessions']} | {previous['total_sessions']} | {render_comparison(current['total_sessions'], previous['total_sessions'])} |",
            f"| Total work time | {format_minutes(current['total_minutes'])} | {format_minutes(previous['total_minutes'])} | {render_comparison(current['total_minutes'], previous['total_minutes'])} |",
            f"| Tool invocations | {current['total_tool_calls']} | {previous['total_tool_calls']} | {render_comparison(current['total_tool_calls'], previous['total_tool_calls'])} |",
            "",
            "## Project Distribution",
            "",
            "| Project | Sessions | Work Time | Ratio |",
            "| --- | --- | --- | --- |",
            *project_lines,
            "",
            "## Work Type Analysis",
            "",
            "| Type | Sessions | Ratio |",
            "| --- | --- | --- |",
            *type_lines,
            "",
            "## Jira Activity",
            "",
            "| Issue | Sessions | Work Time |",
            "| --- | --- | --- |",
            *jira_lines,
            "",
            "## Daily Activity",
            "",
            "| Date | Sessions | Work Time |",
            "| --- | --- | --- |",
            *day_lines,
            "",
            "## Notes",
            "",
            "- Data source: `~/.codex/sessions` session logs only.",
            "- Work types are heuristic and derived from prompts plus tool usage.",
            "- If a session has incomplete timestamps, its duration may be understated.",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    env = load_env_config(REPO_ROOT / "env.config")
    window = parse_week_window(args.week)
    previous_window = parse_week_window(current_week_label(window.monday - timedelta(days=7)))

    report = render_report(window, aggregate(window), aggregate(previous_window))
    if args.stdout:
        print(report)
        return 0

    output_path = resolve_output_path(env, window.week_label)
    output_path.write_text(report, encoding="utf-8")
    print(f"Created weekly analytics: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
