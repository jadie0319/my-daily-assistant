# Directory Access Rules

This file defines the absolute rules for directory access and modification across different tools in this project.

## Absolute Rules

### Directory Ownership

1. **Claude Code** MUST NOT modify the `.codex` directory
   - Can only read/inspect `.codex` directory contents
   - All modifications to `.codex` are strictly prohibited

2. **Codex** MUST NOT modify the `.claude` directory
   - Can only read/inspect `.claude` directory contents
   - All modifications to `.claude` are strictly prohibited

3. **Each tool can ONLY modify its own designated directory**
   - Claude Code → `.claude` directory only
   - Codex → `.codex` directory only

### Shared Resources

4. **Root-level shared files** can be modified by both tools
   - Files in the project root (e.g., `CLAUDE.md`, `AGENTS.md`, `env.config`, etc.)
   - Any file outside `.claude` and `.codex` directories
   - These are considered common/shared resources

### Read Access

5. **Cross-directory inspection is allowed**
   - Both tools can read/inspect each other's directories
   - Read-only access to understand context and configurations
   - No modification permitted across boundaries

## Summary

| Tool | Can Modify | Can Read | Cannot Modify |
|------|------------|----------|---------------|
| Claude Code | `.claude/`, root files | `.claude/`, `.codex/`, root files | `.codex/` |
| Codex | `.codex/`, root files | `.codex/`, `.claude/`, root files | `.claude/` |

## Enforcement

These rules are absolute and must be followed at all times. Violations should be immediately flagged and corrected.
