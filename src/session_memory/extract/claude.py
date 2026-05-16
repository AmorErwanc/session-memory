"""Claude Code session jsonl 抽取(L0.5)。

只保留:用户真输入 + AI 最终回复(stop_reason=end_turn 等)。
砍掉:tool_use / tool_result / thinking / attachment / system / 等。
"""

from __future__ import annotations
from pathlib import Path

from .common import iter_jsonl, trim_ts, deduplicate_cwd


CMD_PREFIXES = (
    "<local-command-stdout>", "<local-command-caveat>",
    "<command-name>", "<command-message>", "<command-args>",
)


def extract(path: Path) -> dict:
    """从 Claude jsonl 抽取干净对话,返回 dict(可直接 dump_yaml)。"""
    messages = []
    session_id = path.stem

    for row in iter_jsonl(path):
        t = row.get("type")
        cwd = row.get("cwd")
        ts = trim_ts(row.get("timestamp"))

        if t == "user":
            # 自动注入的压缩前情摘要不算用户输入
            if row.get("isCompactSummary"):
                continue

            msg = row.get("message", {}) or {}
            content = msg.get("content")
            if content is None:
                continue

            # 字符串 content:可能是 slash 命令系统注入,过滤
            if isinstance(content, str):
                s = content.strip()
                if not s:
                    continue
                if s.startswith(CMD_PREFIXES):
                    continue
                messages.append({"role": "user", "ts": ts, "cwd": cwd, "text": s})
                continue

            # 列表 content:抽 text 项
            if isinstance(content, list):
                texts = []
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        tx = (part.get("text") or "").strip()
                        if tx:
                            texts.append(tx)
                if texts:
                    messages.append({
                        "role": "user", "ts": ts, "cwd": cwd,
                        "text": "\n".join(texts),
                    })

        elif t == "assistant":
            msg = row.get("message", {}) or {}
            content = msg.get("content", []) or []
            stop_reason = msg.get("stop_reason")
            # 只留最终回复(end_turn/stop_sequence/无 stop_reason)
            # tool_use 是中间汇报,丢
            is_final = stop_reason in (None, "end_turn", "stop_sequence")
            if not is_final:
                continue

            texts = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    tx = (part.get("text") or "").strip()
                    if tx:
                        texts.append(tx)
            if texts:
                messages.append({
                    "role": "assistant", "ts": ts, "cwd": cwd,
                    "text": "\n".join(texts),
                })

    data = {
        "source": "claude",
        "original_file": str(path),
        "session_id": session_id,
        "messages": messages,
    }
    return deduplicate_cwd(data)
