"""Assemble only explicit public files and source-free core wheels for release."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tarfile
import zipfile
from pathlib import Path

VERSION = "2.0.0"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-312", type=Path, required=True)
    parser.add_argument("--core-313", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    target = args.output.resolve()
    target.mkdir(mode=0o700, parents=True)
    for name in (
        "unified_setup.py",
        "install-unified.sh",
        "client-requirements.lock",
        "e5-assets.sha256.json",
        "reranker-assets.sha256.json",
        "install-client.sh",
        "README.ko.md",
        "GENERATION-CONTRACT.ko.md",
        "UNIFIED-RUNTIME.ko.md",
    ):
        shutil.copy2(root / name, target / name)
    shutil.copy2(root.parent / "mcp-local/setup.py", target / "runtime-helper.py")
    manifest = {"version": VERSION, "files": {}}
    (target / "packages").mkdir()
    for label, wheel in (
        ("core_312", args.core_312),
        ("core_313", args.core_313),
        ("sdk", args.sdk),
    ):
        with zipfile.ZipFile(wheel) as archive:
            metadata = [
                n for n in archive.namelist() if n.endswith(".dist-info/METADATA")
            ]
            if (
                len(metadata) != 1
                or f"Version: {VERSION}\n" not in archive.read(metadata[0]).decode()
            ):
                raise ValueError("Wheel version does not match release")
            if label.startswith("core"):
                python_tag = "cp312" if label == "core_312" else "cp313"
                if wheel.name.split("-")[-3] != python_tag:
                    raise ValueError(f"{label} requires a {python_tag} wheel")
                for name in archive.namelist():
                    if name.endswith((".c", ".h")) or (
                        name.endswith(".py")
                        and name
                        not in {
                            "agents_memory/__init__.py",
                            "agents_memory/runtime_launcher.py",
                        }
                    ):
                        raise ValueError("Private source must not enter the release")
        destination = "packages/" + wheel.name
        shutil.copy2(wheel, target / destination)
        manifest[label] = destination
    for path in sorted(target.rglob("*")):
        if path.is_file():
            with path.open("rb") as stream:
                manifest["files"][path.relative_to(target).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
    (target / "ASSETS.json").write_text(json.dumps(manifest, indent=2) + "\n")
    archive_path = target.parent / (target.name + ".tar.gz")
    with tarfile.open(archive_path, "w:gz") as archive:
        for path in sorted(target.rglob("*")):
            if path.is_file():
                archive.add(
                    path, arcname=path.relative_to(target).as_posix(), recursive=False
                )
    with archive_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    archive_path.with_suffix(archive_path.suffix + ".sha256").write_text(
        digest + "  " + archive_path.name + "\n"
    )
    print(
        json.dumps(
            {"archive": str(archive_path), "sha256": digest, "private_sources": False}
        )
    )


if __name__ == "__main__":
    main()
