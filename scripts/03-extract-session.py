"""
03-extract-session.py
从指定的 JSONL 会话文件中提取完整的用户消息流。

用法:
    python 03-extract-session.py <session-file>                  # 提取所有用户消息
    python 03-extract-session.py <session-file> --first 5        # 只看前5条
    python 03-extract-session.py <session-file> --last 5         # 只看后5条
    python 03-extract-session.py <session-file> --stats          # 统计信息
    python 03-extract-session.py <session-file> --timeline       # 时间线视图

    # 通过项目名+关键词快速定位
    python 03-extract-session.py --project exomind --grep "AI-CONTEXT"
    python 03-extract-session.py --project ACA --grep "小车" --first 3

依赖: 仅 Python 标准库
"""

import json
import os
import glob
import argparse
from datetime import datetime
from pathlib import Path


def iter_session_records(session_path):
    """逐行迭代会话记录"""
    with open(session_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                record = json.loads(line)
                yield record
            except json.JSONDecodeError:
                continue


def extract_text(content):
    """从 content 字段提取纯文本"""
    if isinstance(content, str):
        return content.strip()
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "").strip()
    return ""


def get_session_messages(session_path, include_assistant=False):
    """
    提取会话中的消息流。

    返回: list of dict with keys: type, text, timestamp
    """
    messages = []
    for record in iter_session_records(session_path):
        msg_type = record.get("type")
        if msg_type not in ("user", "assistant"):
            continue

        msg = record.get("message", {})
        if not isinstance(msg, dict):
            continue

        text = extract_text(msg.get("content", ""))
        timestamp = record.get("timestamp", "")

        if not text:
            continue

        # 过滤噪音
        if msg_type == "user" and (text.startswith("<local-command") or text.startswith("<command")):
            continue

        if msg_type == "user" or include_assistant:
            messages.append({
                "type": msg_type,
                "text": text,
                "timestamp": timestamp,
            })

    return messages


def find_session_by_project(project_keyword, file_keyword=None):
    """通过项目名关键词查找会话文件"""
    projects_dir = Path.home() / ".claude" / "projects"

    matches = []
    for proj_dir in sorted(projects_dir.iterdir()):
        if not proj_dir.is_dir():
            continue
        if project_keyword.lower() in proj_dir.name.lower():
            sessions = sorted(proj_dir.glob("*.jsonl"), key=lambda s: s.stat().st_mtime, reverse=True)
            for s in sessions:
                if file_keyword:
                    # 搜索会话内容中是否包含关键词
                    msgs = get_session_messages(s, include_assistant=True)
                    content = " ".join(m["text"] for m in msgs[:20])
                    if file_keyword.lower() in content.lower():
                        matches.append(s)
                        break
                else:
                    matches.append(s)
                    break  # 每个项目只取最新的

    return matches


def cmd_extract(args):
    """提取消息"""
    if args.project:
        sessions = find_session_by_project(args.project, args.grep)
        if not sessions:
            print(f"未找到匹配 '{args.project}' 的项目会话")
            return
        session_path = sessions[0]
        print(f"定位到: {session_path.parent.name}/{session_path.name}\n")
    else:
        session_path = Path(args.session_file)
        if not session_path.exists():
            print(f"文件不存在: {session_path}")
            return

    messages = get_session_messages(session_path, include_assistant=args.assistant)

    # 应用过滤
    if args.first:
        messages = messages[:args.first]
    elif args.last:
        messages = messages[-args.last:]

    if args.grep and not args.project:
        messages = [m for m in messages if args.grep.lower() in m["text"].lower()]

    if args.stats:
        all_msgs = get_session_messages(session_path, include_assistant=True)
        user_msgs = [m for m in all_msgs if m["type"] == "user"]
        asst_msgs = [m for m in all_msgs if m["type"] == "assistant"]
        print(f"会话统计:")
        print(f"  用户消息: {len(user_msgs)}")
        print(f"  助手消息: {len(asst_msgs)}")
        print(f"  总消息数: {len(all_msgs)}")
        if user_msgs:
            print(f"  首条时间: {user_msgs[0]['timestamp']}")
            print(f"  末条时间: {user_msgs[-1]['timestamp']}")
        return

    if args.timeline:
        all_msgs = get_session_messages(session_path, include_assistant=False)
        print(f"时间线 (共 {len(all_msgs)} 条用户消息):\n")
        for m in all_msgs:
            ts = m["timestamp"][:16] if m["timestamp"] else "?"
            print(f"  [{ts}] {m['text'][:120]}")
        return

    # 默认输出
    print(f"共 {len(messages)} 条消息:\n")
    for i, m in enumerate(messages, 1):
        prefix = "👤" if m["type"] == "user" else "🤖"
        ts = m["timestamp"][:16] if m["timestamp"] else "?"
        # 截断长消息
        text = m["text"][:300].replace("\n", " ")
        if len(m["text"]) > 300:
            text += "..."
        print(f"{i:3d}. {prefix} [{ts}] {text}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="提取 Claude Code 会话内容")
    parser.add_argument("session_file", nargs="?", help="JSONL 会话文件路径")
    parser.add_argument("--project", help="按项目名关键词查找")
    parser.add_argument("--grep", help="按内容关键词过滤")
    parser.add_argument("--first", type=int, help="只显示前N条")
    parser.add_argument("--last", type=int, help="只显示后N条")
    parser.add_argument("--stats", action="store_true", help="显示统计信息")
    parser.add_argument("--timeline", action="store_true", help="时间线视图")
    parser.add_argument("--assistant", action="store_true", help="包含助手回复")
    args = parser.parse_args()

    if not args.session_file and not args.project:
        parser.print_help()
    else:
        cmd_extract(args)
