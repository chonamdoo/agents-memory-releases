"""Check or start the official, preinstalled Hindsight reference profile (stdlib only)."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
TOOLS = (
    "retain", "sync_retain", "recall", "get_document", "delete_document", "get_memory",
    "list_memories", "list_documents", "get_operation", "list_operations",
)
PROFILE = {
    "DATABASE_SCHEMA": "hindsight_reference",
    "RETAIN_EXTRACTION_MODE": "chunks",
    "RETAIN_CHUNK_SIZE": "3000",
    "ENABLE_OBSERVATIONS": "false",
    "ENABLE_AUTO_CONSOLIDATION": "false",
    "EMBEDDINGS_PROVIDER": "onnx",
    "EMBEDDINGS_ONNX_MODEL_ID": "intfloat/multilingual-e5-small",
    "EMBEDDINGS_ONNX_DIMENSIONS": "384",
    "EMBEDDINGS_ONNX_MAX_TOKENS": "512",
    "EMBEDDINGS_ONNX_POOLING": "mean",
    "EMBEDDINGS_ONNX_NORMALIZE": "true",
    "EMBEDDINGS_ONNX_QUERY_PREFIX": "query: ",
    "EMBEDDINGS_ONNX_PASSAGE_PREFIX": "passage: ",
    "EMBEDDINGS_ONNX_BATCH_SIZE": "16",
    "EMBEDDINGS_ONNX_CPU_MEM_ARENA": "false",
    "EMBEDDINGS_ONNX_DEVICE": "cpu",
    "RERANKER_PROVIDER": "rrf",
    "WORKER_ENABLED": "true",
    "WORKER_MAX_SLOTS": "1",
    "WORKER_CONSOLIDATION_RESERVED_SLOTS": "0",
    "WORKER_MAX_RETRIES": "0",
    "MCP_ENABLED": "true",
    "MCP_ENABLED_TOOLS": ",".join(TOOLS),
    "OTEL_TRACES_ENABLED": "false",
    "LLM_TRACE_ENABLED": "false",
    "LOG_LEVEL": "info",
    "DECISION_MODEL_PROVIDER": "none",
}
for _role in ("", "RETAIN_", "REFLECT_", "CONSOLIDATION_", "MENTAL_MODEL_REFRESH_"):
    PROFILE[f"{_role}LLM_PROVIDER"] = "none"
    PROFILE[f"{_role}LLM_MAX_RETRIES"] = "0"
OFFLINE = {
    "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
    "TOKENIZERS_PARALLELISM": "false", "PYTHON_DOTENV_DISABLED": "1",
}


def assets(directory: str) -> Path:
    path = Path(directory)
    if (not path.is_absolute() or "://" in directory or directory.startswith("/absolute/path/to/")
            or any(part.startswith("NEW_") for part in path.parts)):
        raise ValueError("Use an existing absolute private asset directory, without placeholders")
    root = path.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Asset directory is missing")
    manifest = json.loads((HERE / "e5-assets.sha256.json").read_text())
    if set(manifest) != {
        "model.onnx", "tokenizer.json", "config.json", "tokenizer_config.json",
        "special_tokens_map.json",
    }:
        raise ValueError("Unexpected E5 asset manifest")
    for name, expected in manifest.items():
        file = (root / name).resolve(strict=True)
        if not file.is_relative_to(root) or not file.is_file():
            raise ValueError("E5 asset must be a regular file inside the asset directory")
        with file.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"E5 asset checksum mismatch: {name}")
    return root


def database_url(parent: dict[str, str]) -> str:
    # Never interpolate the value into exceptions, stdout, argv, or configuration examples.
    value = parent.get("DATABASE_URL", "")
    try:
        parsed = urlsplit(value)
        # Match asyncpg's URL decoding before deciding which database may be migrated.
        name = unquote(parsed.path[1:], errors="strict") if parsed.path.startswith("/") else ""
        placeholder = name.casefold() in {
            "database", "database_name", "dbname", "your_database", "your_db",
            "new_database_url", "new_database_name", "new_database", "new_db",
            "your_database_name", "your_db_name", "placeholder", "changeme", "change_me",
        }
        valid = (
            parsed.scheme in {"postgres", "postgresql"}
            and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
            and parsed.port != 0
            and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,62}", name) is not None
            and not re.search(r"%(?![0-9A-Fa-f]{2})", parsed.path)
            and name.casefold() not in {"postgres", "template0", "template1"}
            and not placeholder
            and not parsed.query and not parsed.fragment
            and not any(character.isspace() for character in value)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError("DATABASE_URL must select an already provisioned local PostgreSQL database")
    return value


def check_ports(host: str, api: int, worker: int) -> None:
    if host != "127.0.0.1":
        raise ValueError("API binding must be 127.0.0.1")
    if api == worker or any(not 1024 <= port <= 65535 for port in (api, worker)):
        raise ValueError("Choose distinct API/worker ports between 1024 and 65535")
    # Bind only; no listen/connect, requests or database activity. Availability is a snapshot.
    for port in (api, worker):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.bind((host, port))
        except OSError:
            raise ValueError("An API/worker port is unavailable") from None


def prepare(args: argparse.Namespace, parent: dict[str, str]) -> tuple[list[str], dict[str, str]]:
    root = assets(args.asset_dir)
    database = database_url(parent)
    check_ports(args.host, args.api_port, args.worker_port)
    executable = shutil.which(args.hindsight_api, path=parent.get("PATH", os.defpath))
    if not executable or not Path(executable).is_file():
        raise ValueError("Official hindsight-api executable is unavailable; install separately")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", args.bank):
        raise ValueError("Use a new bank name with letters, digits, underscores or hyphens")
    child = {key: value for key, value in parent.items() if not key.startswith("HINDSIGHT_API_")}
    child.update({f"HINDSIGHT_API_{key}": value for key, value in PROFILE.items()})
    child.update(OFFLINE)
    child.update({
        "HINDSIGHT_API_DATABASE_URL": database,
        "HINDSIGHT_API_HOST": args.host,
        "HINDSIGHT_API_PORT": str(args.api_port),
        "HINDSIGHT_API_WORKER_HTTP_PORT": str(args.worker_port),
        "HINDSIGHT_API_EMBEDDINGS_ONNX_MODEL_PATH": str(root / "model.onnx"),
        "HINDSIGHT_API_EMBEDDINGS_ONNX_TOKENIZER_NAME_OR_PATH": str(root),
    })
    for key in ("NO_PROXY", "no_proxy"):
        child[key] = ",".join(filter(None, [child.get(key, ""), "127.0.0.1,localhost,::1"]))
    return [str(Path(executable).absolute()), "--host", args.host, "--port", str(args.api_port)], child


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 11):  # noqa: UP036 - standalone helper runs outside project installs
        print("The local reference launcher requires Python 3.11 or newer.", file=sys.stderr)
        return 2
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Read-only checks; no process or DB calls")
    mode.add_argument("--start", action="store_true", help="Exec official API; it may migrate supplied DB")
    parser.add_argument("--asset-dir", required=True)
    parser.add_argument("--api-port", type=int, required=True)
    parser.add_argument("--worker-port", type=int, required=True)
    parser.add_argument("--bank", required=True, help="New project bank used in printed MCP URL")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--hindsight-api", default="hindsight-api", help="Preinstalled official executable")
    args = parser.parse_args(argv)
    try:
        command, child = prepare(args, dict(os.environ))
    except (OSError, ValueError, TypeError):
        # OS/parser messages may include caller data: keep diagnostics bounded and secret-free.
        print("Preflight failed: check local assets/checksums, DATABASE_URL, ports, bank and executable.",
              file=sys.stderr)
        return 2
    print("Local reference preflight passed (assets, configuration and ports; no DB connection).")
    print(f"Bank MCP: http://127.0.0.1:{args.api_port}/mcp/{args.bank}/", flush=True)
    if args.start:
        try:
            os.execve(command[0], command, child)
        except OSError:
            print("Official API could not be executed.", file=sys.stderr)
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
