"""L1.1 抽取(第一次调用):session yaml → digest yaml。"""

from __future__ import annotations
import json
import time
from pathlib import Path

from ..adapters.claude_cli import call_claude
from ..utils.json_extract import extract_json
from ..utils.yaml_io import dump_yaml


def generate_one(yaml_path: Path, out_path: Path, prompt: str,
                 model: str = "opus", max_retries: int = 2,
                 timeout: int = 600) -> dict:
    """
    对单个 session yaml 跑 L1.1,产出 digest yaml。

    Returns:
        dict with keys: status / in_size / out_size / elapsed / attempts / error?
    """
    yaml_content = yaml_path.read_text()
    in_size = len(yaml_content)

    payload = f"## SESSION YAML(以下是要分析的 session)\n\n{yaml_content}"

    last_err = None
    for attempt in range(max_retries + 1):
        start = time.time()
        raw, err = call_claude(prompt, payload, model=model, timeout=timeout)
        elapsed = time.time() - start

        if raw is None:
            last_err = err
            if attempt < max_retries:
                time.sleep(2)
            continue

        json_str = extract_json(raw)
        if json_str is None:
            last_err = f"no JSON block; raw head: {raw[:200]!r}"
            _save_raw_debug(raw, yaml_path.stem, "nojson")
            if attempt < max_retries:
                time.sleep(2)
            continue

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            last_err = f"JSON parse error: {e}"
            _save_raw_debug(raw, yaml_path.stem, "parseerror")
            if attempt < max_retries:
                time.sleep(2)
            continue

        if not isinstance(data, dict):
            last_err = f"not a dict: {type(data).__name__}"
            _save_raw_debug(raw, yaml_path.stem, "notdict")
            if attempt < max_retries:
                time.sleep(2)
            continue

        # 成功
        dump_yaml(data, out_path)
        return {
            "status": "ok",
            "in_size": in_size,
            "out_size": out_path.stat().st_size,
            "elapsed": elapsed,
            "attempts": attempt + 1,
        }

    return {
        "status": "failed",
        "error": last_err,
        "in_size": in_size,
        "out_size": 0,
        "elapsed": 0.0,
        "attempts": max_retries + 1,
    }


def _save_raw_debug(raw: str, stem: str, suffix: str):
    """失败时把 raw 写到 tmp/ 方便排查。"""
    tmp_dir = Path("/Users/edy/program/session-memory/tmp")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    debug_path = tmp_dir / f"l1_raw_{int(time.time()*1000)}_{stem[:30]}_{suffix}.txt"
    try:
        debug_path.write_text(raw)
    except Exception:
        pass
