"""claude -p 命令行调用封装。"""

from __future__ import annotations
import subprocess


def call_claude(prompt: str, payload: str, model: str = "opus",
                timeout: int = 600) -> tuple[str | None, str | None]:
    """
    调用 `claude -p --model <model>`,把 prompt+payload 拼接传入。

    Returns:
        (stdout, None) 成功 / (None, error_msg) 失败
    """
    full_input = f"{prompt}\n\n---\n\n{payload}"
    try:
        result = subprocess.run(
            # --no-session-persistence:本工具的 LLM 调用不污染本机 session 历史
            # (否则每次 L1 调用都被记录成新 session,会被 session-memory 自己扫到)
            ["claude", "-p", full_input, "--model", model, "--no-session-persistence"],
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return None, "timeout"

    if result.returncode != 0:
        return None, f"exit={result.returncode}; stderr={result.stderr[:300]}"

    raw = result.stdout
    if not raw.strip():
        return None, "empty output"

    return raw, None
