# session-review

Codex / Claude Code session radar for recovering work context across both platforms.

This skill scans local Codex and Claude Code JSONL histories, builds a unified session index, and helps an Agent answer questions such as:

- What sessions were active recently?
- Which thread should I resume next?
- How do I recover CLI windows after a terminal crash?
- Which Codex or Claude Code session matches this UUID?

## Quick Start

```bash
python scripts/session_review.py --days 7
python scripts/session_review.py --days 1 --action-view
python scripts/session_review.py --days 1 --restore-view --shell powershell
python scripts/session_review.py --session <uuid>
python scripts/session_review.py --json
```

## Skill Entry

Use `SKILL.md` as the Agent-facing instruction file. The main script is:

```text
scripts/session_review.py
```

The old Claude-only scripts are kept for compatibility, but the unified entry is recommended.
