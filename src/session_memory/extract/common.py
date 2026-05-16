"""L0.5 共用工具:cwd 去重、文件名规范化、jsonl 读取。"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Iterable


def iter_jsonl(path: Path) -> Iterable[dict]:
    """逐行读 jsonl,坏行跳过。"""
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def trim_ts(ts):
    """'2026-05-10T05:03:32.727Z' → '2026-05-10T05:03:32Z'(去毫秒)。"""
    if not ts or not isinstance(ts, str):
        return ts
    if "." in ts:
        return ts.split(".")[0] + "Z"
    return ts


def deduplicate_cwd(data: dict) -> dict:
    """
    去掉 messages 里重复的 cwd,顶层加 initial_cwd,
    后续 message 只在 cwd 变化时才标。
    """
    messages = data.get("messages", [])
    if not messages:
        return data

    initial_cwd = None
    for msg in messages:
        if msg.get("cwd"):
            initial_cwd = msg["cwd"]
            break

    if not initial_cwd:
        return data

    last_cwd = initial_cwd
    for msg in messages:
        msg_cwd = msg.get("cwd")
        if msg_cwd is None:
            continue
        if msg_cwd == last_cwd:
            del msg["cwd"]
        else:
            last_cwd = msg_cwd

    return {
        "source": data["source"],
        "original_file": data["original_file"],
        "session_id": data["session_id"],
        "initial_cwd": initial_cwd,
        "messages": data["messages"],
    }


def normalize_ts_for_filename(ts) -> str:
    """'2026-05-10T05:03:32Z' → '2026-05-10T05-03-32'(精度到秒,防文件名冲突)。"""
    if not ts:
        return "unknown-time"
    return ts[:19].replace(":", "-")
