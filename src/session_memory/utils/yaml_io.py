"""YAML 读写工具,统一长字符串走 | 块字面量,中文不转义。"""

from __future__ import annotations
from pathlib import Path
import yaml


def _str_representer(dumper, data):
    """长字符串或多行 → 块字面量(|),保留原文不堆 \\n。"""
    if "\n" in data or len(data) > 80:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, _str_representer)


def dump_yaml(data, path: Path):
    """写 YAML 文件,中文不转义,长字符串走块字面量,字典顺序保留。"""
    with path.open("w") as f:
        yaml.dump(
            data, f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
            width=100000,
        )


def load_yaml(path: Path):
    """读 YAML 文件。"""
    with path.open() as f:
        return yaml.safe_load(f)
