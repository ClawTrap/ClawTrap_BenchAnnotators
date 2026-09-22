#!/usr/bin/env python3
"""Build lossless runtime previews without touching benchmark source files."""
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / "runtime_assets"
    output.mkdir(exist_ok=True)
    target = output / "previews.zip"
    temporary = output / "previews.tmp"
    hashes = {}
    original_bytes = 0
    with zipfile.ZipFile(temporary, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for mode in ("clean_assets", "attack_assets"):
            directory = ROOT / "new_data" / mode
            if not directory.is_dir():
                raise RuntimeError(f"Missing preview sources: {mode}")
            for path in sorted(directory.rglob("*")):
                if not path.is_file():
                    continue
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
    print(json.dumps({"verified_files": len(hashes), "original_bytes": original_bytes,
                      "bundle_bytes": target.stat().st_size}))


if __name__ == "__main__":
    main()
