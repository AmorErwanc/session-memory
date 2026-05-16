"""L1 批处理:并行跑 generate(L1.1)和 clean(L1.2)。"""

from __future__ import annotations
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from .generate import generate_one
from .clean import clean_one


PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


def _worker_generate(args):
    in_path, out_dir, prompt, model, skip_existing = args
    out_path = out_dir / in_path.name.replace(".yaml", ".digest.yaml")
    if skip_existing and out_path.exists():
        return (in_path.name, "skipped", 0, 0, 0.0, 0)
    result = generate_one(in_path, out_path, prompt, model=model)
    return (in_path.name, result["status"], result.get("in_size", 0),
            result.get("out_size", 0), result.get("elapsed", 0.0),
            result.get("attempts", 0), result.get("error"))


def _worker_clean(args):
    digest_path, out_dir, prompt, model, skip_existing = args
    out_path = out_dir / digest_path.name
    if skip_existing and out_path.exists():
        return (digest_path.name, "skipped", 0, 0, 0.0, 0)
    result = clean_one(digest_path, out_path, prompt, model=model)
    return (digest_path.name, result["status"], result.get("in_size", 0),
            result.get("out_size", 0), result.get("elapsed", 0.0),
            result.get("attempts", 0), result.get("error"))


def run_generate(sessions_dir: Path, digests_raw_dir: Path,
                 model: str = "opus", workers: int = 8,
                 force: bool = False) -> dict:
    """L1.1:把 sessions_dir 下所有 yaml 跑成 raw digest。"""
    digests_raw_dir.mkdir(parents=True, exist_ok=True)
    prompt = (PROMPTS_DIR / "l1_extract.md").read_text()

    targets = sorted(sessions_dir.glob("*.yaml"))
    if not targets:
        print(f"没有 session yaml: {sessions_dir}")
        return {"total": 0, "ok": 0, "skipped": 0, "failed": 0}

    skip_existing = not force
    print(f"L1.1 generate:{len(targets)} 个 session,model={model},并发={workers},"
          f"{'增量' if skip_existing else '强制全跑'}")
    print(f"输出:{digests_raw_dir}\n")

    tasks = [(p, digests_raw_dir, prompt, model, skip_existing) for p in targets]
    ok = skipped = failed = 0
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_worker_generate, t) for t in tasks]
        for fut in as_completed(futures):
            name, status, in_sz, out_sz, elapsed, tries, *err = fut.result()
            if status == "ok":
                ok += 1
                print(f"  ✅ {name}  ({in_sz//1024}KB→{out_sz//1024}KB / {elapsed:.0f}s / {tries}次)")
            elif status == "skipped":
                skipped += 1
                print(f"  ⏭️  {name}  (已存在,跳过)")
            else:
                failed += 1
                err_msg = err[0] if err else status
                print(f"  ❌ {name}  {err_msg}")

    wall = time.time() - t0
    print(f"\n完成 L1.1:{ok} ok / {skipped} 跳 / {failed} 失败  总耗时 {wall:.0f}s")
    return {"total": len(targets), "ok": ok, "skipped": skipped, "failed": failed}


def run_clean(digests_raw_dir: Path, digests_cleaned_dir: Path,
              model: str = "opus", workers: int = 8,
              force: bool = False) -> dict:
    """L1.2:把 digests_raw_dir 下所有 digest 跑 review 出 cleaned。"""
    digests_cleaned_dir.mkdir(parents=True, exist_ok=True)
    prompt = (PROMPTS_DIR / "l1_review.md").read_text()

    targets = sorted(digests_raw_dir.glob("*.yaml"))
    if not targets:
        print(f"没有 raw digest: {digests_raw_dir}")
        return {"total": 0, "ok": 0, "skipped": 0, "failed": 0}

    skip_existing = not force
    print(f"L1.2 clean:{len(targets)} 个 digest,model={model},并发={workers},"
          f"{'增量' if skip_existing else '强制全跑'}")
    print(f"输出:{digests_cleaned_dir}\n")

    tasks = [(p, digests_cleaned_dir, prompt, model, skip_existing) for p in targets]
    ok = skipped = failed = 0
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=workers) as ex:
        futures = [ex.submit(_worker_clean, t) for t in tasks]
        for fut in as_completed(futures):
            name, status, in_sz, out_sz, elapsed, tries, *err = fut.result()
            if status == "ok":
                ok += 1
                print(f"  ✅ {name}  ({in_sz//1024}KB→{out_sz//1024}KB / {elapsed:.0f}s / {tries}次)")
            elif status == "skipped":
                skipped += 1
                print(f"  ⏭️  {name}  (已存在,跳过)")
            else:
                failed += 1
                err_msg = err[0] if err else status
                print(f"  ❌ {name}  {err_msg}")

    wall = time.time() - t0
    print(f"\n完成 L1.2:{ok} ok / {skipped} 跳 / {failed} 失败  总耗时 {wall:.0f}s")
    return {"total": len(targets), "ok": ok, "skipped": skipped, "failed": failed}
