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
            ["claude", "-p", full_input, "--model", model],
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
