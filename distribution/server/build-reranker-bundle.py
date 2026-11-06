"""Package the prepared, canonical reranker without downloading or converting it."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import tarfile
from pathlib import Path

VERSION = "2.0.0"
MANIFEST_SHA256 = "ed763f2e78be09613874392d5729fdd1831a1bdd12d094d76d8f6a1dfa62d5d2"
MODEL_SHA256 = "838c5f31e2cc50385c55693d2960edbae41f9f8bf8257e93bce80bc15ae919ea"
MODEL_FILES = {
    "config.json",
    "model.onnx",
    "sentencepiece.bpe.model",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    manifest_path = root / "reranker-assets.sha256.json"
    if manifest_path.is_symlink():
        raise ValueError("Canonical manifest must not be a symbolic link")
    manifest_bytes = manifest_path.read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Canonical reranker manifest changed")
    expected = json.loads(manifest_bytes)
    if set(expected) != MODEL_FILES or expected["model.onnx"] != MODEL_SHA256:
        raise ValueError("Unexpected canonical reranker assets")
    source = args.model_dir.expanduser().absolute()
    if source.resolve(strict=True) != source or not source.is_dir():
        raise ValueError("Model directory must be a real directory without symbolic links")
    target = args.output.expanduser().absolute()
    if target.resolve() != target:
        raise ValueError("Output path must not contain symbolic links or parent traversal")
    archive_path = target.parent / (target.name + ".tar.gz")
    checksum_path = archive_path.with_suffix(archive_path.suffix + ".sha256")
    for path in (target, archive_path, checksum_path):
        if path.exists() or path.is_symlink():
            raise ValueError("Output must be new: " + str(path))
    provenance_path = root / "reranker-provenance.json"
    license_path = root / "LICENSE.reranker.Apache-2.0.txt"
    for path in (provenance_path, license_path):
        if path.is_symlink() or not path.is_file():
            raise ValueError("Companion provenance and license must be regular files")
    provenance = json.loads(provenance_path.read_text())
    if (provenance.get("distributed_onnx_sha256") != MODEL_SHA256
            or provenance.get("license") != "Apache-2.0"):
        raise ValueError("Companion provenance does not match the approved model")
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    created_target = False
    created_archive = False
    created_checksum = False
    try:
        source_fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            if set(os.listdir(source_fd)) != MODEL_FILES:
                raise ValueError("Model directory must contain exactly the six canonical files")
            target.mkdir(mode=0o700)
            created_target = True
            model = target / "model"
            model.mkdir(mode=0o700)
            for name, digest in sorted(expected.items()):
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=source_fd)
                with os.fdopen(fd, "rb") as stream:
                    if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                        raise ValueError("Model asset must be a regular file: " + name)
                    actual = hashlib.sha256()
                    with (model / name).open("xb") as output:
                        os.chmod(model / name, 0o600)
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            actual.update(chunk)
                            output.write(chunk)
                    if actual.hexdigest() != digest:
                        raise ValueError("Canonical model hash mismatch: " + name)
            if set(os.listdir(source_fd)) != MODEL_FILES:
                raise ValueError("Model directory changed while packaging")
        finally:
            os.close(source_fd)
        (target / "reranker-assets.sha256.json").write_bytes(manifest_bytes)
        shutil.copyfile(provenance_path, target / "PROVENANCE.json")
        shutil.copyfile(license_path, target / "LICENSE.Apache-2.0.txt")
        assets = {"version": VERSION, "files": {}}
        for path in sorted(target.rglob("*")):
            if path.is_file():
                with path.open("rb") as stream:
                    assets["files"][path.relative_to(target).as_posix()] = hashlib.file_digest(stream, "sha256").hexdigest()
        (target / "ASSETS.json").write_text(json.dumps(assets, indent=2) + "\n")
        with archive_path.open("xb") as stream:
            created_archive = True
            with tarfile.open(fileobj=stream, mode="w:gz") as archive:
                for path in sorted(target.rglob("*")):
                    if path.is_file():
                        archive.add(path, arcname=path.relative_to(target).as_posix(), recursive=False)
        with archive_path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        with checksum_path.open("x") as stream:
            created_checksum = True
            stream.write(digest + "  " + archive_path.name + "\n")
        print(json.dumps({"archive": str(archive_path), "sha256": digest,
                          "model_dir": str(target / "model"), "version": VERSION}))
    except BaseException:
        if created_checksum:
            checksum_path.unlink()
        if created_archive:
            archive_path.unlink()
        if created_target:
            shutil.rmtree(target)
        raise


if __name__ == "__main__":
    main()
