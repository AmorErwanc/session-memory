"""session-memory CLI 入口(typer)。

装好后系统全局可用:
    sm extract party
    sm digest party
    sm status party
    sm list-projects
    sm clean-tmp
"""

from __future__ import annotations
import shutil
import time
from pathlib import Path
import typer
import yaml as yamllib

from .extract.batch import extract_project
from .digest.batch import run_generate, run_clean


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def _load_config() -> dict:
    with CONFIG_PATH.open() as f:
        return yamllib.safe_load(f)


def _project_root(project: str) -> str:
    cfg = _load_config()
    p = cfg.get("projects", {}).get(project)
    if not p:
        typer.echo(f"❌ 项目未在 config.yaml 中定义: {project}", err=True)
        raise typer.Exit(1)
    return p["root"]


def _path(project: str, key: str) -> Path:
    cfg = _load_config()
    base = PROJECT_ROOT / cfg["paths"][key]
    return base / project


app = typer.Typer(help="session-memory:从 AI CLI 对话历史抽取业务事件摘要。",
                  add_completion=False)


@app.command()
def extract(
    project: str = typer.Argument(None, help="项目名(在 config.yaml 中定义);用 --file 时可省略"),
    file: str = typer.Option(None, "--file", "-f", help="单文件测试模式,传 jsonl 路径"),
    force: bool = typer.Option(False, "--force", help="强制重跑(默认增量)"),
    workers: int = typer.Option(None, "--workers", "-w", help="并发数"),
):
    """L0.5:扫项目下所有 session jsonl,输出干净的 yaml 对话。

    两种模式:
      sm extract party              # 项目模式:扫整个项目
      sm extract --file <jsonl>     # 单文件模式:测试用,输出到 tmp/single-file-test/
    """
    cfg = _load_config()
    workers = workers or cfg["defaults"]["concurrency"]

    # 单文件模式
    if file:
        from .extract import claude as claude_extract
        from .extract import codex as codex_extract
        from .extract.common import normalize_ts_for_filename
        from .utils.yaml_io import dump_yaml

        in_path = Path(file).expanduser().resolve()
        if not in_path.exists():
            typer.echo(f"❌ 文件不存在: {in_path}", err=True)
            raise typer.Exit(1)

        # 用路径判断是 claude 还是 codex
        path_str = str(in_path)
        if "/.claude/" in path_str or "claude" in in_path.name.lower():
            src = "claude"
            data = claude_extract.extract(in_path)
        elif "/.codex/" in path_str or "codex" in in_path.name.lower() or "rollout-" in in_path.name:
            src = "codex"
            data = codex_extract.extract(in_path)
        else:
            typer.echo(f"⚠️ 无法从路径判断是 claude 还是 codex,默认按 claude 试")
            src = "claude"
            data = claude_extract.extract(in_path)

        if not data["messages"]:
            typer.echo(f"⚠️ 抽完是空 session(无用户输入)")
            raise typer.Exit(0)

        out_dir = PROJECT_ROOT / "tmp" / "single-file-test"
        out_dir.mkdir(parents=True, exist_ok=True)
        first_ts = data["messages"][0].get("ts")
        sid = data["session_id"]
        fname = f"{normalize_ts_for_filename(first_ts)}-{src}-{sid[:8]}.yaml"
        out_path = out_dir / fname
        dump_yaml(data, out_path)

        typer.echo(f"\n✅ 单文件抽取完成")
        typer.echo(f"   来源:{in_path}")
        typer.echo(f"   输出:{out_path}")
        typer.echo(f"   消息数:{len(data['messages'])}")
        return

    # 项目模式
    if not project:
        typer.echo("❌ 必须指定 project,或者用 --file 单文件模式", err=True)
        raise typer.Exit(1)

    project_root = _project_root(project)
    out_dir = _path(project, "sessions")

    stats = extract_project(project, project_root, out_dir,
                            force=force, workers=workers)
    typer.echo(f"\n✅ 完成 — {stats}")


@app.command()
def digest(
    project: str = typer.Argument(..., help="项目名"),
    stage: str = typer.Option("all", "--stage", "-s",
                              help="generate / clean / all"),
    model: str = typer.Option(None, "--model", "-m", help="opus / sonnet"),
    workers: int = typer.Option(None, "--workers", "-w", help="并发数"),
    force: bool = typer.Option(False, "--force", help="强制重跑(默认增量)"),
):
    """L1:把 session 转 digest,可选 review-and-rewrite 清洁。"""
    cfg = _load_config()
    model = model or cfg["defaults"]["model"]
    workers = workers or cfg["defaults"]["concurrency"]

    sessions_dir = _path(project, "sessions")
    raw_dir = _path(project, "digests_raw")
    cleaned_dir = _path(project, "digests_cleaned")

    if not sessions_dir.exists() or not list(sessions_dir.glob("*.yaml")):
        typer.echo(f"❌ 没有 session 数据,先跑 `sm extract {project}`", err=True)
        raise typer.Exit(1)

    if stage in ("generate", "all"):
        typer.echo("━━ L1.1 generate ━━")
        run_generate(sessions_dir, raw_dir, model=model, workers=workers, force=force)
        typer.echo("")

    if stage in ("clean", "all"):
        typer.echo("━━ L1.2 clean ━━")
        run_clean(raw_dir, cleaned_dir, model=model, workers=workers, force=force)


@app.command()
def synthesize(
    project: str = typer.Argument(..., help="项目名"),
):
    """L2:跨 session 合成业务事件卡(待开发)。"""
    typer.echo(f"⚠️ L2 synthesize 尚未实施。项目: {project}")
    raise typer.Exit(1)


@app.command()
def status(
    project: str = typer.Argument(..., help="项目名"),
):
    """看某项目当前流水线进度。"""
    sessions = _path(project, "sessions")
    raw = _path(project, "digests_raw")
    cleaned = _path(project, "digests_cleaned")

    def count_and_size(d: Path):
        if not d.exists():
            return 0, 0
        files = list(d.glob("*.yaml"))
        size_kb = sum(f.stat().st_size for f in files) // 1024
        return len(files), size_kb

    n_s, sz_s = count_and_size(sessions)
    n_r, sz_r = count_and_size(raw)
    n_c, sz_c = count_and_size(cleaned)

    typer.echo(f"\n项目: {project}")
    typer.echo(f"  L0.5 sessions:       {n_s:>4} 个  {sz_s:>6} KB  ({sessions})")
    typer.echo(f"  L1.1 digests/raw:    {n_r:>4} 个  {sz_r:>6} KB  ({raw})")
    typer.echo(f"  L1.2 digests/cleaned:{n_c:>4} 个  {sz_c:>6} KB  ({cleaned})")
    typer.echo("")
    if n_s > 0:
        pct_r = n_r / n_s * 100
        pct_c = n_c / n_s * 100
        typer.echo(f"  覆盖率:L1.1 {pct_r:.0f}%  L1.2 {pct_c:.0f}%")


@app.command("list-projects")
def list_projects():
    """列 config.yaml 中定义的所有项目。"""
    cfg = _load_config()
    projects = cfg.get("projects", {})
    typer.echo(f"\n共 {len(projects)} 个项目:\n")
    for name, info in projects.items():
        desc = info.get("description", "")
        typer.echo(f"  {name:<20} {info['root']}")
        if desc:
            typer.echo(f"  {'':<20} ↳ {desc}")
    typer.echo("")


@app.command()
def doctor():
    """检查环境配置是否正确(claude CLI、uv、Python、各项目根目录等)。"""
    import shutil as _shutil
    import sys

    typer.echo("\n=== session-memory 环境自检 ===\n")
    issues = []

    # Python 版本
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    typer.echo(f"  Python:        {py_ver}  {'✅' if py_ok else '❌ 需要 >= 3.10'}")
    if not py_ok:
        issues.append("Python 版本过低")

    # claude CLI
    claude_path = _shutil.which("claude")
    typer.echo(f"  claude CLI:    {claude_path or '❌ 找不到'}  {'✅' if claude_path else ''}")
    if not claude_path:
        issues.append("claude CLI 不在 PATH(L1 会失败)")

    # uv
    uv_path = _shutil.which("uv")
    typer.echo(f"  uv:            {uv_path or '⚠️  没装(开发可选)'}")

    # 项目根
    typer.echo(f"  项目根:        {PROJECT_ROOT}  {'✅' if PROJECT_ROOT.exists() else '❌'}")

    # config.yaml
    typer.echo(f"  config.yaml:   {CONFIG_PATH}  {'✅' if CONFIG_PATH.exists() else '❌'}")
    if not CONFIG_PATH.exists():
        issues.append("config.yaml 不存在")

    # prompts
    prompts_dir = PROJECT_ROOT / "prompts"
    p1 = prompts_dir / "l1_extract.md"
    p2 = prompts_dir / "l1_review.md"
    typer.echo(f"  l1_extract.md: {p1}  {'✅' if p1.exists() else '❌'}")
    typer.echo(f"  l1_review.md:  {p2}  {'✅' if p2.exists() else '❌'}")
    if not p1.exists() or not p2.exists():
        issues.append("prompts 文件缺失")

    # 数据目录
    for sub in ["data/sessions", "data/digests/raw", "data/digests/cleaned",
                "data/events", "logs", "tmp"]:
        d = PROJECT_ROOT / sub
        typer.echo(f"  {sub:<22} {'✅' if d.exists() else '⚠️ 不存在(会自动创建)'}")

    typer.echo("")

    # 项目配置
    try:
        cfg = _load_config()
        projects = cfg.get("projects", {})
        typer.echo(f"  === 项目配置({len(projects)} 个) ===")
        for name, info in projects.items():
            root = info.get("root", "")
            root_exists = Path(root).exists() if root else False
            mark = "✅" if root_exists else "❌ 根目录不存在"
            typer.echo(f"    {name:<20} {root}  {mark}")
            if root_exists:
                # 看下数据
                s_dir = _path(name, "sessions")
                r_dir = _path(name, "digests_raw")
                c_dir = _path(name, "digests_cleaned")
                ns = len(list(s_dir.glob("*.yaml"))) if s_dir.exists() else 0
                nr = len(list(r_dir.glob("*.yaml"))) if r_dir.exists() else 0
                nc = len(list(c_dir.glob("*.yaml"))) if c_dir.exists() else 0
                typer.echo(f"    {'':<20} sessions={ns}  raw={nr}  cleaned={nc}")
    except Exception as e:
        issues.append(f"config.yaml 解析失败: {e}")

    typer.echo("")
    if issues:
        typer.echo(f"❌ 发现 {len(issues)} 个问题:")
        for i, msg in enumerate(issues, 1):
            typer.echo(f"  {i}. {msg}")
        raise typer.Exit(1)
    else:
        typer.echo("✅ 全部检查通过")


@app.command()
def failures(
    limit: int = typer.Option(20, "--limit", "-n", help="显示最近 N 条"),
    show: int = typer.Option(None, "--show", "-s", help="显示第 N 条的 raw 内容"),
):
    """看 L1 抽取失败的 raw 输出(在 tmp/ 下)。"""
    tmp_dir = PROJECT_ROOT / "tmp"
    if not tmp_dir.exists():
        typer.echo("tmp/ 不存在")
        return

    # 同时扫 L1.1 (l1_raw_*) 和 L1.2 (l1clean_raw_*)
    raw_files = sorted(
        list(tmp_dir.glob("l1_raw_*.txt")) + list(tmp_dir.glob("l1clean_raw_*.txt")),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    if not raw_files:
        typer.echo("✅ 没有失败记录")
        return

    if show is not None:
        if show < 1 or show > len(raw_files):
            typer.echo(f"❌ --show {show} 越界,共 {len(raw_files)} 条", err=True)
            raise typer.Exit(1)
        f = raw_files[show - 1]
        typer.echo(f"\n=== 第 {show} 条:{f.name} ===")
        typer.echo(f"路径:{f}")
        typer.echo(f"大小:{f.stat().st_size} 字节")
        typer.echo("内容头部 1000 字:")
        typer.echo("---")
        typer.echo(f.read_text()[:1000])
        typer.echo("---")
        return

    typer.echo(f"\n共 {len(raw_files)} 条失败记录(显示最近 {min(limit, len(raw_files))} 条):\n")
    for i, f in enumerate(raw_files[:limit], 1):
        # 文件名格式:l1_raw_<timestamp_ms>_<reason>.txt 或 l1_raw_<ts>_<stem>_<reason>.txt
        parts = f.stem.split("_")
        reason = parts[-1] if len(parts) >= 3 else "?"
        mtime = time.strftime("%Y-%m-%d %H:%M", time.localtime(f.stat().st_mtime))
        size = f.stat().st_size
        typer.echo(f"  {i:>3}. [{mtime}] {reason:<12} {size:>6} 字节  {f.name}")

    typer.echo(f"\n用 `sm failures --show N` 看第 N 条的 raw 内容")


@app.command("clean-tmp")
def clean_tmp(
    days: int = typer.Option(7, "--days", "-d", help="删除 N 天前的文件"),
):
    """清理 tmp/ 下的旧调试文件。"""
    tmp_dir = PROJECT_ROOT / "tmp"
    if not tmp_dir.exists():
        typer.echo("tmp/ 不存在")
        return
    cutoff = time.time() - days * 86400
    deleted = 0
    for f in tmp_dir.iterdir():
        if f.name == ".gitkeep":
            continue
        try:
            if f.stat().st_mtime < cutoff:
                if f.is_dir():
                    shutil.rmtree(f)
                else:
                    f.unlink()
                deleted += 1
        except Exception as e:
            typer.echo(f"  ⚠️ 删除失败 {f.name}: {e}")
    typer.echo(f"已删除 {deleted} 个 {days} 天前的文件")


if __name__ == "__main__":
    app()
