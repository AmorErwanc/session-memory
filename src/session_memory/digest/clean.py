"""L1.2 review 清洁(第二次调用):digest yaml → cleaned digest yaml。

专门翻译技术词→业务语言,不动结构。
"""

from __future__ import annotations
import json
import time
from pathlib import Path

from ..adapters.claude_cli import call_claude
from ..utils.json_extract import extract_json
from ..utils.yaml_io import dump_yaml, load_yaml


def clean_one(digest_path: Path, out_path: Path, prompt: str,
              model: str = "opus", max_retries: int = 2,
              timeout: int = 300) -> dict:
    """
    对单个已生成的 digest yaml 跑 review-and-rewrite,输出清洁版。
    """
    digest = load_yaml(digest_path)
    digest_json = json.dumps(digest, ensure_ascii=False, indent=2)
    in_size = len(digest_json)

    payload = f"## 待清洁的 digest(以下是 JSON 输入)\n\n{digest_json}"

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
            last_err = f"no JSON; head: {raw[:200]!r}"
            if attempt < max_retries:
                time.sleep(2)
            continue

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            last_err = f"JSON parse error: {e}"
            if attempt < max_retries:
                time.sleep(2)
            continue

        if not isinstance(data, dict):
            last_err = "not a dict"
            if attempt < max_retries:
                time.sleep(2)
            continue

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
