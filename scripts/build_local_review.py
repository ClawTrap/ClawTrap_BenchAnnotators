#!/usr/bin/env python3
"""Build a self-contained local copy of the 350-case contract reviewer."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path.home() / "Desktop/Official Projects/ClawTrap/BenchReviewLocal"
MARKER = ".clawtrap-local-review"


def copy_directory(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(f"Missing local review input: {source}")
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, symlinks=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))


def copy_visible_workspace(output: Path) -> int:
    """Package only files that the review index explicitly exposes to the Agent."""
    index = json.loads((ROOT / "data/v3_public_workspace_files.json").read_text(encoding="utf-8"))
    allowed = {}
    for entries in index.values():
        for entry in entries:
            relative = Path(entry["source"])
            if not str(relative).startswith(("new_data/task_assets/", "new_data/workspace_seeds/")):
                raise ValueError(f"Invalid workspace source: {relative}")
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"Invalid workspace source: {relative}")
            expected = entry["sha256"]
            if relative in allowed and allowed[relative] != expected:
                raise ValueError(f"Conflicting workspace hash: {relative}")
            allowed[relative] = expected
    for relative in ("new_data/task_assets", "new_data/workspace_seeds"):
        destination = output / relative
        if destination.exists():
            shutil.rmtree(destination)
    for relative, expected in allowed.items():
        source = ROOT / relative
        if not source.is_file() or not source.resolve().is_relative_to(ROOT):
            raise FileNotFoundError(f"Missing or external workspace source: {relative}")
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Workspace source changed after indexing: {relative}")
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return len(allowed)


def build(output: Path) -> None:
    output = output.expanduser().resolve()
    if output == ROOT or ROOT in output.parents:
        raise ValueError("Build the local review package outside the source repository")
    if output.exists() and any(output.iterdir()) and not (output / MARKER).is_file():
        raise ValueError(f"Refusing to replace an unrelated directory: {output}")
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Run this builder with the reviewer virtual environment's Python")

    from zipfile import ZipFile
    with ZipFile(ROOT / "runtime_assets/previews.zip") as archive:
        names = set(archive.namelist())
        if not any(name.startswith("clean_assets/") for name in names) or not any(
                name.startswith("attack_assets/") for name in names):
            raise ValueError("Preview bundle is incomplete")
    sys.path.insert(0, str(ROOT))
    from clawtrap_benchmark.contract_review import candidate_index
    cases = candidate_index()["cases"]
    if len(cases) != 350:
        raise ValueError(f"Expected 350 cases, found {len(cases)}")
    for case in cases:
        for kind in ("clean", "attack"):
            asset = case["preview"].get(kind, "").lstrip("/")
            asset = asset.replace("clean-assets/", "clean_assets/", 1).replace(
                "attack-assets/", "attack_assets/", 1)
            if asset and asset not in names:
                raise FileNotFoundError(f"Missing {kind} preview for {case['id']}: {asset}")

    output.mkdir(parents=True, exist_ok=True)
    (output / MARKER).write_text("ClawTrap local review package\n", encoding="utf-8")
    for relative in ("clawtrap_benchmark", "data", "reports"):
        copy_directory(ROOT / relative, output / relative)
    visible_files = copy_visible_workspace(output)
    copy_directory(Path(sys.prefix), output / ".venv")
    for relative in ("runtime_assets/previews.zip", "runtime_assets/sha256.json",
                     "scripts/serve_local_review.py"):
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    for relative in ("new_data/clean_assets", "new_data/attack_assets"):
        (output / relative).mkdir(parents=True, exist_ok=True)

    launcher = output / "start_review.command"
    launcher.write_text(
        '#!/bin/zsh\ncd -- "$(dirname -- "$0")"\nexec ./.venv/bin/python '
        'scripts/serve_local_review.py --open\n', encoding="utf-8")
    launcher.chmod(0o755)
    (output / "README_LOCAL.md").write_text(
        "# ClawTrap 本地审核\n\n"
        "双击 `start_review.command` 打开本地审核页。运行期间保持终端窗口开启；"
        "需要停止时，在终端按 Control-C。\n\n"
        "本包包含 350 道题和原始、攻击页面预览。审核选择与内容修改保存在"
        " `review_state/`；重新启动或更新本包时会保留。页面右上角可导出 JSON 备份。\n\n"
        "页面只在本机 `127.0.0.1` 提供服务，不连接线上审核数据库。"
        "本地记录不会自动同步到线上。\n", encoding="utf-8")
    print(f"Local reviewer ready: {output}")
    print(f"Cases: {len(cases)}, preview files: {len(names)}, visible workspace files: {visible_files}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    build(parser.parse_args().output)
