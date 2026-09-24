#!/usr/bin/env python3
"""Build lossless runtime previews without touching benchmark source files."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def verify_public_workspace_files():
    index = json.loads((ROOT / "data/v3_public_workspace_files.json").read_text(encoding="utf-8"))
    count = 0
    for entries in index.values():
        for entry in entries:
            source = entry["source"]
            if not source.startswith(("new_data/task_assets/", "new_data/workspace_seeds/")) or ".." in Path(source).parts:
                raise RuntimeError(f"Invalid public workspace file path: {source}")
            path = ROOT / source
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise RuntimeError(f"Missing or changed public workspace file: {source}")
            count += 1
    return count


def main():
    workspace_file_count = verify_public_workspace_files()
    preview_index = ROOT / 'data/v3_preview_asset_index.json'
    if preview_index.is_file():
        declared = json.loads(preview_index.read_text(encoding='utf-8'))
        if declared.get('version') != 'clawtrap.v3.preview-assets.v1':
            raise RuntimeError('Unexpected v3 preview asset index')
        relative_assets = declared['assets']
        if len(relative_assets) != len(set(relative_assets)):
            raise RuntimeError('Duplicate v3 preview asset path')
        sources = []
        for relative in relative_assets:
            path = Path(relative)
            if (not relative.startswith(('new_data/clean_assets/', 'new_data/attack_assets/'))
                or '..' in path.parts or path.is_absolute()):
                raise RuntimeError(f'Invalid v3 preview asset path: {relative}')
            source = ROOT / path
            if not source.is_file():
                raise FileNotFoundError(f'Missing v3 preview asset: {relative}')
            sources.append(source)
    else:
        sources = [path for mode in ('clean_assets', 'attack_assets')
                   for path in sorted((ROOT / 'new_data' / mode).rglob('*')) if path.is_file()]
    output = ROOT / "runtime_assets"
    output.mkdir(exist_ok=True)
    target = output / "previews.zip"
    temporary = output / "previews.tmp"
    hashes = {}
    original_bytes = 0
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for path in sorted(sources):
            name = path.relative_to(ROOT / "new_data").as_posix()
            data = path.read_bytes()
            hashes[name] = hashlib.sha256(data).hexdigest()
            original_bytes += len(data)
            info = zipfile.ZipInfo(name)
            info.compress_type = zipfile.ZIP_DEFLATED
            bundle.writestr(info, data, compresslevel=9)
    with zipfile.ZipFile(temporary) as bundle:
        for name, expected in hashes.items():
            if hashlib.sha256(bundle.read(name)).hexdigest() != expected:
                raise RuntimeError(f"Preview bytes changed: {name}")
    temporary.replace(target)
    (output / "sha256.json").write_text(json.dumps(hashes, indent=2) + "\n")
    # Only the review UI is public; snapshots stay behind Flask authentication.
    shutil.copytree(ROOT / "clawtrap_benchmark/static", ROOT / "public/static", dirs_exist_ok=True)
    print(json.dumps({"verified_files": len(hashes), "workspace_files": workspace_file_count,
                      "original_bytes": original_bytes,
                      "bundle_bytes": target.stat().st_size}))


if __name__ == "__main__":
    main()
