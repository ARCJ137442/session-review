---
name: session-review
description: |
  Codex / Claude Code 会话回顾与全景扫描。用于 Terminal 或 App 崩溃后找回工作现场、跨平台检索 session/thread UUID、日常巡视所有项目和线程进展、发现被遗忘的工作线。Use when the user asks to review sessions, scan session history, recover prior work, inspect what was done recently, or locate a Codex/Claude Code session by UUID.
---

# Session Review

统一扫描 Codex 与 Claude Code 会话，生成“工作现场索引”。默认综合两个平台；`--platform` 只用于过滤范围。

## Session Skill Boundary

- `session-review`：全景扫描、UUID 定位、行动队列、窗口恢复命令。
- `session-extract`：对某个明确 session/thread 生成详细交接报告。
- 已废弃的 `claude-code-session-extract` 与 `codex-rollout-extract` 不再作为入口；遇到旧文档或历史提示时，改用本 skill 或 `session-extract`。

## Quick Start

脚本位于本 skill 的 `scripts/` 目录。Agent 在任意 workspace 被触发时，必须先解析当前 `SKILL.md` 所在目录，再使用统一入口：

```bash
python <skill_dir>/scripts/session_review.py --days 7
```

`<skill_dir>` 是当前 `SKILL.md` 所在目录。只有在人工调试且已经 `cd` 到本 skill 根目录时，才可以临时使用相对 `scripts/` 路径；面向任意项目的说明和 Agent 执行都必须使用可定位的 `<skill_dir>/scripts/session_review.py`。

常用命令：

```bash
# 默认：Codex + Claude Code 综合扫描
python <skill_dir>/scripts/session_review.py

# 平台过滤
python <skill_dir>/scripts/session_review.py --platform codex --days 1
python <skill_dir>/scripts/session_review.py --platform claude --days 7

# 跨平台 UUID/session/thread 定位
python <skill_dir>/scripts/session_review.py --session <uuid>
python <skill_dir>/scripts/session_review.py --uuid <uuid>

# 过滤与机器可读输出
python <skill_dir>/scripts/session_review.py --project exomind --grep issue
python <skill_dir>/scripts/session_review.py --group-by cwd
python <skill_dir>/scripts/session_review.py --detail
python <skill_dir>/scripts/session_review.py --action-view
python <skill_dir>/scripts/session_review.py --restore-view --shell powershell
python <skill_dir>/scripts/session_review.py --json
```

## Core Rules

1. **先综合，后过滤。** 未指定 `--platform` 时必须同时扫描 Codex 与 Claude Code；`--platform codex|claude` 只是缩小范围。
2. **UUID 不要求用户知道平台。** 收到 session/thread UUID 时，先跑 `python <skill_dir>/scripts/session_review.py --session <uuid>`，让脚本跨平台定位。
3. **执行入口必须可定位。** Agent 在任意 workspace 被触发时，先解析本 skill 目录，再用绝对路径运行 `<skill_dir>/scripts/session_review.py`。
4. **Codex UUID 本体只看 `session_meta.payload.id`。** 文件名、`parent_thread_id`、`forked_from_id` 只能作为线索或关联关系，不能替代主身份；`--session <uuid>` 必须聚合所有 `payload.id == uuid` 的 rollout。
5. **默认入口是 `session_review.py`。** 旧脚本 `02-scan-all-projects.py`、`03-extract-session.py`、`04-quick-overview.sh` 保留兼容，但不作为首选。
6. **只读会话历史。** 不修改、不删除 `.jsonl`、`.sqlite` 或任何历史会话文件。
7. **验证才算完成。** 修改 skill 或脚本后，至少运行 Codex、Claude、默认综合、JSON、UUID 相关验证中的代表性命令。

## Never Rules

- **NEVER** 只靠 Codex rollout 文件名判断 thread id；同一 thread 可能出现在文件名不含该 id 的 rollout 中。
- **NEVER** 把 `parent_thread_id` 或 `forked_from_id` 命中混同为目标 session 本体；它们只说明关联。
- **NEVER** 为了摘要读取 encrypted reasoning、base64 图片或大块 tool output；这些内容会污染输出并拖慢扫描。
- **NEVER** 修改、清理、重写任何历史会话文件；本 skill 只生成索引视图。
- **NEVER** 在未知当前目录时直接假设 `scripts/session_review.py` 可用；先定位 `<skill_dir>`。

## Inputs

| 参数 | 默认 | 说明 |
|------|------|------|
| `--platform all|codex|claude` | `all` | 平台过滤器，不指定时综合扫描 |
| `--days N` | `7` | 最近 N 天，`0` 表示全部 |
| `--session <uuid>` | - | 跨平台定位 UUID |
| `--uuid <uuid>` | - | `--session` 别名 |
| `--project <keyword>` | - | 过滤 title/display_name/cwd/id |
| `--grep <keyword>` | - | 过滤可读用户/agent 文本 |
| `--group-by thread|cwd` | `thread` | 默认线程/项目视图；`cwd` 聚合工作目录 |
| `--detail` | false | 逐条展开每个会话，适合避免遗漏 |
| `--action-view` | false | 输出“下一步行动队列”，按接手价值排序 |
| `--restore-view` | false | 输出可复制的恢复命令，适合 Terminal 崩溃后恢复窗口 |
| `--shell auto|powershell|bash|all` | `auto` | 恢复命令的 shell；Windows 自动用 PowerShell |
| `--limit N` | `12` | `--action-view` / `--restore-view` 的候选上限，`0` 表示全部 |
| `--codex-cli <cmd>` | `codex` | 自定义 Codex CLI 命令名或路径 |
| `--claude-cli <cmd>` | `claude` | 自定义 Claude Code CLI 命令名或路径 |
| `--json` | false | 输出统一 JSON 数组 |

## Output

默认 Markdown 表格：

```text
状态 | 来源 | 线程/项目 | 工作目录 | 最后活跃 | 轮数 | 摘要
```

JSON 输出字段：

```text
platform, id, title, cwd, display_name, last_active,
days_since_active, status, user_turns, agent_turns,
session_count_or_rollout_count, total_size_mb,
first_message, last_message, summary
```

详细 Markdown 输出：

```bash
python <skill_dir>/scripts/session_review.py --days 7 --detail
python <skill_dir>/scripts/session_review.py --platform codex --days 1 --detail
python <skill_dir>/scripts/session_review.py --project exomind --detail
```

每条会话会展开：

```text
标题、状态、来源、ID、工作目录、最后活跃、用户/Agent 轮数、
session/rollout 数、总大小、摘要、来源文件、首条可读消息、末条可读消息
```

行动队列输出：

```bash
python <skill_dir>/scripts/session_review.py --days 7 --action-view
python <skill_dir>/scripts/session_review.py --platform codex --days 1 --action-view --limit 8
```

用于回答：“我现在该接哪几条线？”脚本会根据最近活跃、中断/等待/继续信号、工作量、通知/子代理噪音降权，输出可解释的排序和下一步建议。

恢复窗口输出：

```bash
python <skill_dir>/scripts/session_review.py --days 7 --restore-view --shell powershell
python <skill_dir>/scripts/session_review.py --days 7 --restore-view --shell bash
python <skill_dir>/scripts/session_review.py --days 7 --restore-view --shell all
```

用于 Windows Terminal 或 shell 窗口崩溃后恢复 CLI 工作现场。输出包括：

```text
1. 任意位置直接复制的 cd + resume 一行命令
2. 按工作目录分组的 cd 一次 + 多条 resume 命令
3. PowerShell 下额外给 Windows Terminal wt new-tab 命令
```

恢复命令约定：

```text
Codex: codex resume <thread-id>
Claude Code: claude --resume <session-id>
```

如果本机 CLI 命令名不同，使用 `--codex-cli` 或 `--claude-cli` 覆盖。
Windows 路径优先使用 PowerShell 输出；Bash 输出主要用于 macOS/Linux/WSL/Git Bash 等环境。

## Reporting Rules

- 优先直接转述脚本输出的事实：总记录数、日期范围、平台、标题、工作目录、最后活跃时间、轮数。
- 不要重新心算或改写脚本 header 中的日期；报告日期范围必须以脚本原文为准。
- 若要二次归纳项目分布或 TOP 列表，必须说明是“归纳/估计”，不要把未精确计算的 `~N` 当成脚本事实。
- 当用户只是要“看一周全景”时，先给高信号概览；深入某个 session 时再建议 `session-extract`。
- 当用户说“展开每个会话”“逐个检查”“避免遗漏”“详细列举”时，使用 `--detail`；若记录过多，先加 `--platform`、`--project`、`--days` 或 `--grep` 缩小范围。
- `--detail` 仍是索引级展开，不是完整交接；某条会话需要接手时，再对该 id 使用 `session-extract`。
- 当用户说“我现在该做什么”“立马进入行动”“哪些线要接”时，使用 `--action-view`。
- 当用户说“Windows Terminal 崩了”“CLI 窗口状态丢了”“给我恢复命令”时，使用 `--restore-view`，Windows 优先 `--shell powershell`。
- 恢复命令只生成，不自动执行；不要替用户打开多个终端窗口，除非用户明确要求。

## Data Sources

Codex：

```text
~/.codex/sessions/**/*.jsonl
~/.codex/archived_sessions/**/*.jsonl
~/.codex/session_index.jsonl
```

Claude Code：

```text
~/.claude/projects/**/*.jsonl
```

## Adapter Behavior

Codex adapter:

- 按 `session_meta.payload.id` 聚合同一 thread 的多个 rollout 文件。
- `--session <uuid>` 二阶段定位：扫描候选 rollout 的 `session_meta.payload.id`，再聚合同一 id 的所有命中文件；不只看文件名。
- 从 `session_index.jsonl` 读取最新 `thread_name`，同一 id 多次出现时取最新更新时间。
- 只解析白名单字段：`session_meta`、`event_msg/user_message`、`event_msg/agent_message`、`event_msg/task_complete`、可读 assistant message。
- 跳过 encrypted reasoning、图片/base64、大块 tool output，避免污染摘要和拖慢扫描。
- 超大 rollout 文件采用头尾采样，保证全景扫描快速返回；需要精确交接报告时改用 `session-extract`。

Claude adapter:

- 继续按 `~/.claude/projects/<encoded-project>/` 聚合。
- 复用原有项目名美化、摘要提炼、状态标签、焦点提示思路。
- `--session` 命中 Claude Code 单个 JSONL 时输出单会话记录。

## Known Pitfalls

| 坑 | 应对 |
|----|------|
| Codex 文件名形如 `rollout-YYYY-MM-DDTHH-MM-SS-<id>.jsonl` | 不手搜，使用 `--session <uuid>` |
| 同一 Codex thread id 可能有多份 rollout | adapter 按 id 聚合 |
| 文件名不含目标 UUID，但 `session_meta.payload.id` 属于目标 UUID | `--session` 必须解析 metadata 后纳入聚合 |
| UUID 出现在 `parent_thread_id` / `forked_from_id` | 这是关联会话，不是目标本体 |
| `session_index.jsonl` 同一 id 可能重复 | 取最新 `updated_at` 的标题 |
| Codex JSONL 可能含大量 encrypted reasoning / base64 图片 | 只读白名单字段 |
| 最近 7 天 Codex 历史可能达到数 GB | 全景扫描对超大 rollout 采样；精确恢复用 `session-extract` |
| Claude Code 与 Codex 聚合维度不同 | 默认统一成线程/项目记录，必要时 `--group-by cwd` |

## Validation Checklist

修改本 skill 后运行。若未 `cd` 到本 skill 根目录，使用 `<skill_dir>/scripts/...` 绝对路径：

```bash
python -m py_compile <skill_dir>/scripts/scan_common.py <skill_dir>/scripts/scan_codex.py <skill_dir>/scripts/scan_claude.py <skill_dir>/scripts/session_review.py
python <skill_dir>/scripts/session_review.py --platform codex --days 1
python <skill_dir>/scripts/session_review.py --platform claude --days 7
python <skill_dir>/scripts/session_review.py --days 7
python <skill_dir>/scripts/session_review.py --days 1 --detail
python <skill_dir>/scripts/session_review.py --days 1 --action-view
python <skill_dir>/scripts/session_review.py --days 1 --restore-view --shell powershell
python -c "import json, subprocess; out=subprocess.check_output(['python',r'<skill_dir>/scripts/session_review.py','--json']); json.loads(out.decode('utf-8-sig')); print('json-ok')"
```

若需要验证 UUID：

```bash
python <skill_dir>/scripts/session_review.py --session <known-codex-thread-id>
python <skill_dir>/scripts/session_review.py --session <known-claude-session-id>
```

Codex UUID 聚合回归检查：

```bash
python <skill_dir>/scripts/session_review.py --session <known-codex-thread-id> --json
python <skill_dir>/scripts/session_review.py --platform codex --days 1 --json
```

同一 id 在两种输出里的 `rollout_count`、`user_turns`、`agent_turns` 应一致；若不一致，优先检查 `session_meta.payload.id` 检索是否漏文件。
