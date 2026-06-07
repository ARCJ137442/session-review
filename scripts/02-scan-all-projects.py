"""
02-scan-all-projects.py (v0.2.0)
扫描 ~/.claude/projects/ 下所有项目，按最近活跃时间排序，
提取每个项目最新会话的首/末用户消息。支持内容量自适应输出。

v0.2 新增:
  - R9:  项目名美化 (beautify_project_name)
  - R10: 默认 Markdown 表格输出
  - R11: 时间分组 (今天/昨天/最近)
  - R12: 焦点提示层 (热点/遗忘风险/关联项目)
  - R13: 摘要提炼 (generate_summary)

用法:
    python 02-scan-all-projects.py              # 默认: 近7天, 表格输出
    python 02-scan-all-projects.py --days 14    # 近14天
    python 02-scan-all-projects.py --all        # 全部（不限时间）
    python 02-scan-all-projects.py --json       # JSON 输出（供程序消费）

依赖: 仅 Python 标准库
"""

import json
import os
import re
import argparse
from datetime import datetime, timedelta
from pathlib import Path

SCRIPT_VERSION = "0.3.0"

# ── 噪音前缀 (R4) ──────────────────────────────────────────
NOISE_PREFIXES = (
    "<local-command",
    "<command",
    "Base directory for this skill:",
    "```\nBase directory",
)

# ── 项目名美化 (R9) ────────────────────────────────────────
# 路径中的父目录关键词，用于跳过
PARENT_KEYWORDS = {
    "develop", "projects", "repos", "workspace", "src",
    "code", "work", "home", "user", "users", "docs",
}

# 太短或纯数字的段名，用于兜底取倒数第二段
SKIP_SEGMENTS_MIN_LEN = 2


def beautify_project_name(name):
    """
    R9: 将编码路径中的项目名转换为人类可读简称。

    示例:
        "H--Example-Develop-AGI-exomind" -> "exomind"
        "my-cool-project" -> "my-cool-project"
        "H--Example-Develop-project-v2" -> "project"
        "G--Downloads-Reticulum" -> "Downloads-Reticulum" (保留上下文消歧)
    """
    # 步骤 1: 替换路径分隔符
    normalized = name.replace("--", "/").replace("-", "/")

    # 步骤 2: 分割为段
    segments = [s for s in normalized.split("/") if s]

    # 步骤 3: 过滤父目录关键词
    filtered = [s for s in segments if s.lower() not in PARENT_KEYWORDS]

    # 步骤 4: 如果过滤后为空，回退到原始 segments 的最后一段
    if not filtered:
        filtered = segments

    # 步骤 5: 取最后一段
    candidate = filtered[-1]

    # 步骤 6: 如果最后一段太短（<=2字符）或纯数字，取倒数第二段
    if len(candidate) <= SKIP_SEGMENTS_MIN_LEN or candidate.isdigit():
        if len(filtered) >= 2:
            candidate = filtered[-2]

    # 步骤 7: 消歧 — 如果原始路径有被过滤掉的"上下文关键词"（如 Downloads），
    # 在候选名前加上下文，避免同名不同项目混淆
    context_keywords = {"downloads", "documents", "temp", "backup", "archive"}
    for seg in segments:
        if seg.lower() in context_keywords:
            candidate = f"{seg}-{candidate}"
            break

    # 步骤 8: 如果结果为空或太短，回退到原始 name
    if not candidate or len(candidate) < 1:
        candidate = name

    return candidate


def generate_summary(first_msg, last_msg):
    """
    R13: 从首末消息提炼 ≤10 字中文 / ≤20 字英文摘要。

    压缩策略:
    - 优先保留动词 + 对象
    - 去除语气词、连接词
    - 如果首末消息相同，只用一条
    - URL / HTML标签 / 系统消息 → 固定标签
    """
    if not first_msg and not last_msg:
        return "（无内容）"

    # 如果首末相同，只用一条
    if first_msg and last_msg and first_msg.strip() == last_msg.strip():
        text = first_msg.strip()
    elif first_msg and last_msg:
        # 拼接首末消息的前 50 字符
        text = first_msg.strip()[:50] + " " + last_msg.strip()[:50]
    elif first_msg:
        text = first_msg.strip()
    else:
        text = last_msg.strip()

    # ── R13 前缀检测: 特殊内容直接返回固定标签 ──
    text_stripped = text.strip()
    if text_stripped.startswith(("http://", "https://")):
        return "链接分享"
    if text_stripped.startswith(("<task-notification>", "<task-")):
        return "任务通知"
    if text_stripped.startswith(("<bash-input>",)):
        return "命令执行"
    if text_stripped.startswith(("[Request interrupted", "[Request cancelled")):
        return "中断/取消"

    # 如果消息过短（< 5 字），直接使用原文
    if len(text) <= 5:
        return text

    # 检测语言: 如果主要是中文字符
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    total_chars = len(text.replace(' ', ''))

    is_chinese = total_chars > 0 and chinese_chars / max(total_chars, 1) > 0.3

    if is_chinese:
        # 中文模式: 仅去除多字语气词/短语（保留单字以避免破坏语义）
        cn_phrase_noise = [
            "嗯", "好的", "然后", "接下来", "现在", "我想", "我们",
            "请", "帮我", "可以", "一下", "这个", "那个", "看看",
            "我想", "我需要", "请帮我", "能不能",
        ]
        for phrase in cn_phrase_noise:
            text = text.replace(phrase, "")
        text = re.sub(r'\s+', ' ', text).strip()

        # 中文模式: ≤10 字
        result = ""
        for c in text:
            if result and len(result) >= 10:
                break
            result += c
    else:
        # 英文模式: 去除短语级噪音（不拆单词）
        en_phrase_noise = ["I want", "please", "can you", "let me",
                           "I need", "help me"]
        for phrase in en_phrase_noise:
            text = text.replace(phrase, "")
        # 去除单字噪音（仅在 word boundary 处匹配）
        en_word_noise = ["the", "a", "an", "this", "that"]
        for w in en_word_noise:
            text = re.sub(r'\b' + re.escape(w) + r'\b', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\s+', ' ', text).strip()

        # 英文模式: ≤20 字符
        words = text.split()
        result = ""
        for word in words:
            if result and len(result) + len(word) + 1 > 20:
                break
            result = (result + " " + word).strip()
        if not result:
            result = text[:20]

    # ── 质量兜底 (中英文通用): 如果结果太通用，尝试从原始文本中段提取 ──
    generic_starts = ("Claude", "claude", "帮我", "请帮", "你好", "please", "help")
    raw_first = (first_msg or "").strip()
    if len(result) < 4 or any(result.startswith(g) for g in generic_starts):
        mid = raw_first if raw_first else (last_msg or "").strip()
        if len(mid) > 10:
            segment = mid[10:30]
            alt = ""
            for c in segment:
                if alt and len(alt) >= 10:
                    break
                alt += c
            if len(alt) >= len(result):
                result = alt

    return result


def find_related_projects(results):
    """
    R12-关联: 发现名称相似的项目对。

    检测逻辑:
    1. 两个项目的 display_name 有共同前缀或后缀（>= 4 字符公共部分）
    2. 或两个项目的原始 name 在同一父路径下

    返回: list of (name1, display1, name2, display2, reason)
    """
    related = []
    n = len(results)

    for i in range(n):
        for j in range(i + 1, n):
            p1 = results[i]
            p2 = results[j]
            d1 = p1["display_name"]
            d2 = p2["display_name"]
            n1 = p1["name"]
            n2 = p2["name"]

            # 检测 1: display_name 有 >= 4 字符的公共前缀
            min_len = min(len(d1), len(d2))
            common_prefix = ""
            for k in range(min_len):
                if d1[k] == d2[k]:
                    common_prefix += d1[k]
                else:
                    break
            if len(common_prefix) >= 4:
                related.append((n1, d1, n2, d2, f"共同前缀 '{common_prefix}'"))
                continue

            # 检测 2: display_name 有 >= 4 字符的公共后缀
            common_suffix = ""
            for k in range(1, min_len + 1):
                if d1[-k] == d2[-k]:
                    common_suffix = d1[-k] + common_suffix
                else:
                    break
            if len(common_suffix) >= 4:
                related.append((n1, d1, n2, d2, f"共同后缀 '{common_suffix}'"))
                continue

            # 检测 3: 原始 name 有共同父路径且最后一个 segment 不同
            # Claude 项目名格式: H--Example-Develop-AGI-exomind
            # 只在"仅最后一段不同"时才算关联（如同一仓库的不同子目录）
            sep1 = n1.replace("--", "/").split("/")
            sep2 = n2.replace("--", "/").split("/")
            if len(sep1) >= 3 and len(sep2) >= 3:
                if sep1[:-1] == sep2[:-1] and sep1[-1] != sep2[-1]:
                    # 额外条件：最后一段有共同前缀（避免误匹配不相关项目）
                    last1, last2 = sep1[-1], sep2[-1]
                    min_last = min(len(last1), len(last2))
                    common_last = 0
                    for k in range(min_last):
                        if last1[k] == last2[k]:
                            common_last += 1
                        else:
                            break
                    if common_last >= 3:
                        related.append((n1, d1, n2, d2, f"同一子目录 '{'/'.join(sep1[:-1])}'"))

    return related


def get_time_group(days_since_active):
    """R11: 根据距今天数返回时间分组标签"""
    if days_since_active == 0:
        return "today"
    elif days_since_active == 1:
        return "yesterday"
    elif days_since_active <= 3:
        return "recent"
    else:
        return "older"


def get_time_group_label(group):
    """R11: 返回时间分组的中文标签"""
    labels = {
        "today": "📌 今天活跃",
        "yesterday": "📍 昨天活跃",
        "recent": "🕐 近日活跃",
        "older": "⏳ 更早",
    }
    return labels.get(group, group)


def find_claude_projects_dir():
    """定位 ~/.claude/projects/ 目录"""
    home = Path.home()
    projects_dir = home / ".claude" / "projects"
    if not projects_dir.exists():
        raise FileNotFoundError(f"Claude projects directory not found: {projects_dir}")
    return projects_dir


def is_noise(text):
    """R4: 判断消息是否为噪音"""
    stripped = text.strip()
    for prefix in NOISE_PREFIXES:
        if stripped.startswith(prefix):
            return True
    return False


def extract_user_messages(session_path, limit=None):
    """
    从一个 JSONL 会话文件中提取消息内容。
    应用 R4 噪音过滤。

    返回: list of str (用户文本消息)
    """
    messages = []
    try:
        with open(session_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if record.get("type") != "user":
                    continue

                msg = record.get("message", {})
                if not isinstance(msg, dict):
                    continue

                content = msg.get("content", "")
                text = ""

                if isinstance(content, str):
                    text = content.strip()
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text = block.get("text", "").strip()
                            break

                # R4: 噪音过滤
                if not text or is_noise(text):
                    continue

                messages.append(text)
                if limit and len(messages) >= limit:
                    break
    except Exception:
        pass

    return messages


def get_status_label(days_since_active):
    """R5: 根据距今天数返回状态标签"""
    if days_since_active <= 1:
        return "\U0001f7e2"
    elif days_since_active <= 3:
        return "\U0001f7e1"
    elif days_since_active <= 7:
        return "\U0001f7e0"
    else:
        return "\U0001f534"


def scan_projects(days=7, output_json=False):
    """
    扫描所有活跃项目，返回结构化数据。
    实现 R3 (内容量自适应)、R5 (状态标签)、
    R9 (项目名美化)、R10 (表格化输出)、
    R11 (时间分组)、R12 (焦点提示)、R13 (摘要提炼)。
    """
    projects_dir = find_claude_projects_dir()
    cutoff = datetime.now() - timedelta(days=days) if days > 0 else datetime.min
    now = datetime.now()

    results = []
    for name in sorted(os.listdir(projects_dir)):
        proj_dir = projects_dir / name
        if not proj_dir.is_dir():
            continue

        sessions = list(proj_dir.glob("*.jsonl"))
        if not sessions:
            continue

        latest_session = max(sessions, key=lambda s: s.stat().st_mtime)
        mtime = datetime.fromtimestamp(latest_session.stat().st_mtime)

        if days > 0 and mtime < cutoff:
            continue

        # 统计所有会话的数据
        total_messages = 0
        total_size = 0
        for s in sessions:
            total_size += s.stat().st_size
            try:
                with open(s, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        try:
                            rec = json.loads(line)
                            if rec.get("type") == "user":
                                total_messages += 1
                        except Exception:
                            pass
            except Exception:
                pass

        # 提取最新会话的用户消息 (R3: 自适应)
        latest_msgs = extract_user_messages(latest_session, limit=50)
        msg_count = len(latest_msgs)
        first_msg = latest_msgs[0][:200] if latest_msgs else ""
        last_msg = latest_msgs[-1][:200] if len(latest_msgs) > 1 else ""

        # R5: 状态标签
        days_since = (now - mtime).days
        status = get_status_label(days_since)

        # R9: 项目名美化
        display_name = beautify_project_name(name)

        # R11: 时间分组
        time_group = get_time_group(days_since)

        # R13: 摘要提炼
        summary = generate_summary(first_msg, last_msg)

        results.append({
            "name": name,
            "display_name": display_name,
            "last_active": mtime.strftime("%Y-%m-%d %H:%M"),
            "last_active_ts": mtime.timestamp(),
            "days_since_active": days_since,
            "status": status,
            "time_group": time_group,
            "session_count": len(sessions),
            "total_messages": total_messages,
            "total_size_mb": round(total_size / 1024 / 1024, 1),
            "latest_session_size_kb": round(latest_session.stat().st_size / 1024),
            "latest_msg_count": msg_count,
            "first_message": first_msg,
            "last_message": last_msg,
            "summary": summary,
        })

    results.sort(key=lambda x: x["last_active_ts"], reverse=True)

    if output_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        now_str = now.strftime("%Y-%m-%d")
        start = (now - timedelta(days=days)).strftime("%Y-%m-%d") if days > 0 else "全部"
        print(f"=== Claude Code 会话全景 ({start} ~ {now_str}) ===")
        print(f"=== 共 {len(results)} 个项目 ===\n")

        # ── R11: 按时间分组输出 ──
        # 分离活跃项目 (🟢) 和非活跃项目
        active_projects = [p for p in results if p["status"] == "\U0001f7e2"]
        inactive_projects = [p for p in results if p["status"] != "\U0001f7e2"]

        # 活跃项目按时间分组
        groups = {}
        for p in active_projects:
            g = p["time_group"]
            if g not in groups:
                groups[g] = []
            groups[g].append(p)

        # R10: 表格化输出
        def print_table_header():
            print("| 状态 | 项目 | 最后活跃 | 会话 | 消息 | 摘要 |")
            print("|------|------|----------|------|------|------|")

        def print_table_row(p):
            size_str = (f"{p['total_size_mb']}MB"
                        if p["total_size_mb"] >= 1
                        else f"{p['latest_session_size_kb']}KB")
            print(f"| {p['status']} | {p['display_name']} | {p['last_active']} "
                  f"| {p['session_count']} | {p['total_messages']} | {p['summary']} |")

        # 输出活跃项目分组
        for group_key in ["today", "yesterday", "recent"]:
            if group_key in groups:
                group_projects = groups[group_key]
                print(f"### {get_time_group_label(group_key)}")
                print()
                print_table_header()
                for p in group_projects:
                    print_table_row(p)
                print()

        # 输出非活跃项目 (🟡🟠🔴)
        if inactive_projects:
            print(f"### ⚠️ 需关注")
            print()
            print_table_header()
            for p in inactive_projects:
                print_table_row(p)
            print()

        # ── R12: 焦点提示层 ──
        focus_sections = []

        # 🔥 热点项目
        hot_projects = []
        for p in results:
            is_recent = p["days_since_active"] <= 1
            is_busy = p["session_count"] >= 3 or p["total_messages"] > 100
            if is_recent and is_busy:
                hot_projects.append(p)
        if hot_projects:
            focus_sections.append("🔥 **热点项目**")
            for p in hot_projects[:5]:
                focus_sections.append(
                    f"- **{p['display_name']}** — "
                    f"{p['session_count']} 会话, {p['total_messages']} 消息, "
                    f"{p['summary']}"
                )

        # ⚠️ 遗忘风险
        risk_projects = []
        for p in results:
            # 有活跃会话但 > 5 天未更新
            if p["days_since_active"] > 5 and p["session_count"] > 0:
                risk_projects.append(p)
            # 有 > 10 条消息的会话但 > 7 天未更新
            elif p["days_since_active"] > 7 and p["total_messages"] > 10:
                risk_projects.append(p)
        # 去重
        seen_risk = set()
        unique_risk = []
        for p in risk_projects:
            if p["name"] not in seen_risk:
                seen_risk.add(p["name"])
                unique_risk.append(p)
        if unique_risk:
            focus_sections.append("⚠️ **遗忘风险**")
            for p in unique_risk[:5]:
                focus_sections.append(
                    f"- **{p['display_name']}** — "
                    f"停了 {p['days_since_active']} 天, "
                    f"{p['total_messages']} 消息待续"
                )

        # 🔗 关联项目
        related = find_related_projects(results)
        if related:
            focus_sections.append("🔗 **关联项目**")
            for n1, d1, n2, d2, reason in related[:5]:
                focus_sections.append(
                    f"- **{d1}** <-> **{d2}** — {reason}"
                )

        # 输出焦点提示
        if focus_sections:
            print("---")
            print()
            print("### 焦点提示")
            print()
            for line in focus_sections:
                print(line)
            print()

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="扫描 Claude Code 会话")
    parser.add_argument("--days", type=int, default=7, help="扫描最近N天 (0=全部)")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    parser.add_argument("--version", action="store_true", help="显示版本号")
    args = parser.parse_args()

    if args.version:
        print(f"session-review scan v{SCRIPT_VERSION}")
    else:
        scan_projects(days=args.days, output_json=args.json)
