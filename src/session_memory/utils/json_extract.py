"""从 LLM 输出中抠出 JSON 块,容忍 markdown 包裹和开场白污染。"""

from __future__ import annotations


def extract_json(text: str) -> str | None:
    """
    返回纯 JSON 字符串。
    - 去掉 ```json / ``` 包裹
    - 找第一个 `{` 到最后一个 `}`(防开场白污染)
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:].lstrip()
    elif text.startswith("```"):
        text = text[3:].lstrip()
    if text.endswith("```"):
        text = text[:-3].rstrip()

    first = text.find("{")
    last = text.rfind("}")
    if first == -1 or last == -1 or last < first:
        return None
    return text[first:last + 1]
