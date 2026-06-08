# session-review

Codex / Claude Code session radar for recovering work context across both platforms.

This skill scans local Codex and Claude Code JSONL histories, builds a unified session index, and helps an Agent answer questions such as:

- What sessions were active recently?
- Which thread should I resume next?
- How do I recover CLI windows after a terminal crash?
- Which Codex or Claude Code session matches this UUID?

## Quick Start

This README is for human orientation. Agents should follow `SKILL.md`.

Do not invoke the bundled script through a relative `scripts/...` path from an
arbitrary project workspace. Resolve the installed skill directory first, then
run the script from there.

Windows PowerShell:

```powershell
$skillDir = "$HOME\.claude\skills\session-review"
$review = Join-Path $skillDir "scripts\session_review.py"

python $review --days 7
python $review --days 1 --action-view
python $review --days 1 --restore-view --shell powershell
python $review --session <uuid>
python $review --json
```

macOS / Linux / Git Bash:

```bash
skill_dir="$HOME/.claude/skills/session-review"
review="$skill_dir/scripts/session_review.py"

python3 "$review" --days 7
python3 "$review" --days 1 --action-view
python3 "$review" --days 1 --restore-view --shell bash
python3 "$review" --session <uuid>
python3 "$review" --json
```

## Skill Entry

Use `SKILL.md` as the Agent-facing instruction file. The main script is:

```text
<skill_dir>/scripts/session_review.py
```

`<skill_dir>` means the directory containing this `SKILL.md`.

Use this skill for panoramic session scanning and recovery queues. Use the
`session-extract` skill for detailed handoff extraction from a specific session.
The deprecated `claude-code-session-extract` and `codex-rollout-extract` skills
are no longer part of the local skill set.
