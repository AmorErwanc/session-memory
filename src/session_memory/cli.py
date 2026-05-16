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
    project: str = typer.Argument(..., help="项目名(在 config.yaml 中定义)"),
    file: str = typer.Option(None, "--file", "-f", help="单文件测试模式,传 jsonl 路径"),
    force: bool = typer.Option(False, "--force", help="强制重跑(默认增量)"),
    workers: int = typer.Option(None, "--workers", "-w", help="并发数"),
):
    """L0.5:扫项目下所有 session jsonl,输出干净的 yaml 对话。"""
    cfg = _load_config()
    workers = workers or cfg["defaults"]["concurrency"]

    if file:
        typer.echo(f"⚠️ 单文件模式尚未实现,请用 project 模式")
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
