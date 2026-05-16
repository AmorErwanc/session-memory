"""Codex CLI session jsonl 抽取(L0.5)。

只保留:用户真输入 + AI 最终回复(task_complete 紧前的那条 agent_message)。
砍掉:function_call / function_call_output / reasoning / token_count / 等。
"""

from __future__ import annotations
from pathlib import Path

from .common import iter_jsonl, trim_ts, deduplicate_cwd


def extract(path: Path) -> dict:
    """从 Codex jsonl 抽取干净对话,返回 dict。"""
    rows = list(iter_jsonl(path))

    # 第一遍:找每个 turn 的"最终" agent_message 时间戳
    # (task_complete 或 turn_aborted 紧前的最后一条 agent_message)
    final_ts_raw = set()
    last_agent_ts_raw = None
    in_turn = False
    for row in rows:
        if row.get("type") != "event_msg":
            continue
        ptype = row.get("payload", {}).get("type")
        if ptype == "task_started":
            in_turn = True
            last_agent_ts_raw = None
        elif ptype == "agent_message":
            if in_turn:
                last_agent_ts_raw = row.get("timestamp")
        elif ptype in ("task_complete", "turn_aborted"):
            if last_agent_ts_raw:
                final_ts_raw.add(last_agent_ts_raw)
            in_turn = False
            last_agent_ts_raw = None

    # 第二遍:抽取
    messages = []
    session_id = path.stem
    current_cwd = None

    for row in rows:
        t = row.get("type")
        ts_raw = row.get("timestamp")
        ts = trim_ts(ts_raw)
        payload = row.get("payload", {}) or {}

        if t == "session_meta":
            session_id = payload.get("id") or session_id
            current_cwd = payload.get("cwd") or current_cwd

        elif t == "turn_context":
            new_cwd = payload.get("cwd")
            if new_cwd:
                current_cwd = new_cwd

        elif t == "event_msg":
            ptype = payload.get("type")
            if ptype == "user_message":
                text = (payload.get("message") or payload.get("text") or "").strip()
                if text:
                    messages.append({
                        "role": "user", "ts": ts, "cwd": current_cwd, "text": text,
                    })
            elif ptype == "agent_message":
                if ts_raw not in final_ts_raw:
                    continue
                text = (payload.get("message") or payload.get("text") or "").strip()
                if text:
                    messages.append({
                        "role": "assistant", "ts": ts, "cwd": current_cwd, "text": text,
                    })

    data = {
        "source": "codex",
        "original_file": str(path),
        "session_id": session_id,
        "messages": messages,
    }
    return deduplicate_cwd(data)


def is_session_in_project(path: Path, project_root: str) -> bool:
    """快速检查 codex session 的 cwd 是否在指定项目根目录下。"""
    import json
    try:
        with path.open() as f:
            line = f.readline().strip()
        if not line:
            return False
        d = json.loads(line)
        if d.get("type") != "session_meta":
            return False
        cwd = d.get("payload", {}).get("cwd", "")
        return cwd.startswith(project_root)
    except Exception:
        return False
