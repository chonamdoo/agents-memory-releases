#!/usr/bin/env python3
"""Build both public connector targets using an explicit Go toolchain; no CI dispatch."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/agents-memory-local"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--go", type=Path, required=True)
    parser.add_argument("--postgres-darwin", type=Path, required=True)
    parser.add_argument("--postgres-linux", type=Path, required=True)
    args = parser.parse_args()
    helper = ROOT / "distribution/mcp-local/setup.py"
    contracts = {}
    modules = {}
    for name, path in (("helper", helper), ("contract", ROOT / "tools/check-native-extension.py")):
        spec = importlib.util.spec_from_file_location("connector_build_" + name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        modules[name] = module
    for system, archive in (("Darwin", args.postgres_darwin), ("Linux", args.postgres_linux)):
        filename, expected = modules["helper"].NATIVE_VECTOR[system]
        vector = ROOT / "distribution/mcp-local/assets" / filename
        if digest(vector) != expected:
            raise ValueError("Native extension asset hash differs from the installation pin")
        if digest(archive) != modules["helper"].NATIVE_POSTGRES[system][1]:
            raise ValueError("PostgreSQL archive differs from the installation pin")
        contracts[system] = modules["contract"].verify(archive, vector, system)
    (PLUGIN / "scripts/memory-use.txt").write_text(modules["helper"].MEMORY_USE_INSTRUCTIONS + "\n")
    tool_manifest = PLUGIN / "scripts/memory-tools.json"
    tools = json.loads(tool_manifest.read_text())
    for tool in tools:
        if tool["name"] == "recall":
            tool["description"] = modules["helper"].MEMORY_RECALL_DESCRIPTION
    tool_manifest.write_text(json.dumps(tools, ensure_ascii=False, indent=2) + "\n")
    shutil.copyfile(helper, PLUGIN / "scripts/setup.py")
    source = PLUGIN / "scripts/connector.go"
    source.write_text(re.sub(r'var helperHash = "[^"]+"',
                            'var helperHash = "' + digest(helper) + '"', source.read_text()))
    subprocess.run([str(args.go.with_name("gofmt")), "-w", str(source)], check=True)
    files = {}
    for target, goos, goarch in (("linux-x86_64", "linux", "amd64"), ("darwin-arm64", "darwin", "arm64")):
        output = PLUGIN / "bin" / ("connector-" + target)
        environment = dict(os.environ, GOOS=goos, GOARCH=goarch, CGO_ENABLED="0")
        subprocess.run([str(args.go), "build", "-trimpath", "-ldflags=-s -w", "-o", str(output), str(source)],
                       env=environment, check=True, cwd=ROOT)
        output.chmod(0o755)
        files[output.name] = digest(output)
    connect = PLUGIN / "scripts/connect.sh"
    text = connect.read_text()
    for platform, target in (("Darwin:arm64", "darwin-arm64"), ("Linux:x86_64", "linux-x86_64")):
        text = re.sub(r'(' + platform + r'\) binary=connector-' + target + r'; checksum=)[^ ;]+',
                      r'\g<1>' + files["connector-" + target], text)
    text = re.sub(r'(verify "\$root/scripts/setup.py" )\S+', r'\g<1>' + digest(helper), text)
    connect.write_text(text)
    bootstrap = ROOT / "distribution/mcp-local/install.sh"
    text = re.sub(r'helper_sha=\S+', 'helper_sha=' + digest(helper), bootstrap.read_text())
    for target in ("darwin-arm64", "linux-x86_64"):
        text = re.sub(r'(' + target + r'; connector_sha=)[^ ;]+',
                      r'\g<1>' + files["connector-" + target], text)
    bootstrap.write_text(text)
    shutil.copyfile(bootstrap, PLUGIN / "scripts/install.sh")
    go_version = subprocess.check_output([str(args.go), "version"], text=True).strip()
    (PLUGIN / "bin/AUTO-BUILD.json").write_text(json.dumps({
        "version": "1.0.6", "compiler": go_version, "cgo": False, "source": "../scripts/connector.go",
        "source_sha256": digest(source), "helper_sha256": digest(helper), "files": files,
        "tool_contract_sha256": digest(PLUGIN / "scripts/memory-tools.json"),
        "memory_instructions_sha256": digest(PLUGIN / "scripts/memory-use.txt"),
        "native_extension_contracts": contracts,
        "real_macos_execution": False,
    }, indent=2) + "\n")
    print(json.dumps(files))


if __name__ == "__main__":
    main()
