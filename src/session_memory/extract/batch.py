"""L0.5 批处理:扫整个项目的所有 Claude + Codex session,产出 yaml。"""

from __future__ import annotations
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from . import claude as claude_extract
from . import codex as codex_extract
from .common import normalize_ts_for_filename
from ..utils.yaml_io import dump_yaml


CLAUDE_PROJECTS_DIR = Path("/Users/edy/.claude/projects")
CODEX_SESSIONS_DIR = Path("/Users/edy/.codex/sessions")


def find_claude_files(project_root: str, strict: bool = False) -> list[Path]:
    """找所有 Claude jsonl。

    strict=False(默认):startswith 匹配,包含子目录(如 worktrees)
    strict=True:严格匹配,cwd 必须完全等于 project_root
    """
    # /Users/edy/project/party → -Users-edy-project-party
    folder_prefix = project_root.replace("/", "-")
    files = []
    if not CLAUDE_PROJECTS_DIR.exists():
        return files
    for d in sorted(CLAUDE_PROJECTS_DIR.iterdir()):
        if not d.is_dir():
            continue
        if strict:
            if d.name != folder_prefix:
                continue
        else:
            if not d.name.startswith(folder_prefix):
                continue
        for f in sorted(d.glob("*.jsonl")):
            files.append(f)
    return files


def find_codex_files(project_root: str, strict: bool = False) -> list[Path]:
    """找所有 cwd 在 project_root 下的 codex jsonl(同 strict 语义)。"""
    if not CODEX_SESSIONS_DIR.exists():
        return []
    candidates = sorted(CODEX_SESSIONS_DIR.rglob("*.jsonl"))
    return [f for f in candidates
            if codex_extract.is_session_in_project(f, project_root, strict=strict)]


def _process_one(args):
    """单文件处理(给 worker 用)。"""
    src, in_path, out_dir = args
    try:
        if src == "claude":
            data = claude_extract.extract(in_path)
        else:
            data = codex_extract.extract(in_path)

        # 砍 tool_call(虽然 extract 本来就不输出 tool_call,这里保留兼容性)
        data["messages"] = [m for m in data["messages"] if m.get("role") != "tool_call"]

        n_msg = len(data["messages"])
        if n_msg == 0:
            return (src, in_path, None, 0, "empty")

        first_ts = data["messages"][0].get("ts")
        sid = data["session_id"]
        sid_short = sid[:8] if sid else "unknown"
        fname = f"{normalize_ts_for_filename(first_ts)}-{src}-{sid_short}.yaml"
        out_path = out_dir / fname
        dump_yaml(data, out_path)

        return (src, in_path, out_path, n_msg, "ok")
    except Exception as e:
        return (src, in_path, None, 0, f"error: {e}")


def extract_project(project_name: str, project_root: str, out_dir: Path,
                    force: bool = False, workers: int = 8, strict: bool = False):
    """
    扫指定项目的所有 session jsonl 并抽取为 yaml。

    Args:
        project_name: 项目名(如 "party")
        project_root: 项目根目录(如 "/Users/edy/project/party")
        out_dir: 输出目录(通常是 data/sessions/<project>/)
        force: True 时清空 out_dir 重跑;False 时跳过已存在文件
        workers: 并发数

    Returns:
        dict(stats)
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    if force:
        for f in out_dir.glob("*.yaml"):
            f.unlink()

    mode_str = "strict" if strict else "包含子目录"
    print(f"扫描 session 文件(项目: {project_name}, 根目录: {project_root}, 模式: {mode_str})...")
    claude_files = find_claude_files(project_root, strict=strict)
    codex_files = find_codex_files(project_root, strict=strict)
    print(f"  Claude: {len(claude_files)} 个 jsonl")
    print(f"  Codex:  {len(codex_files)} 个 jsonl")
    total = len(claude_files) + len(codex_files)
    print(f"  总计:   {total} 个")
    print()

    if total == 0:
        print("无文件可处理。")
        return {"total": 0, "ok": 0, "empty": 0, "errors": 0}

    tasks = [("claude", f, out_dir) for f in claude_files] + \
            [("codex", f, out_dir) for f in codex_files]

    print(f"并行提取({workers} workers)...")
    ok = empty = err = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_process_one, t) for t in tasks]
        for fut in as_completed(futures):
            src, in_path, out_path, n_msg, status = fut.result()
            if status == "ok":
                ok += 1
            elif status == "empty":
                empty += 1
            else:
                err += 1
                print(f"  ❌ {src} {in_path.name}: {status}")

    yamls = sorted(out_dir.glob("*.yaml"))
    total_kb = sum(f.stat().st_size for f in yamls) // 1024
    print()
    print(f"完成:{ok} 个有效输出,{empty} 个空 session,{err} 个错误")
    print(f"输出目录:{out_dir} ({len(yamls)} 个 yaml,{total_kb} KB)")

    return {"total": total, "ok": ok, "empty": empty, "errors": err,
            "output_dir": str(out_dir), "output_count": len(yamls)}
