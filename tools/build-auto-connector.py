#!/usr/bin/env python3
"""Build both public connector targets using an explicit Go toolchain; no CI dispatch."""
import argparse
import hashlib
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
    args = parser.parse_args()
    helper = ROOT / "distribution/mcp-local/setup.py"
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
        "version": "1.0.5", "compiler": go_version, "cgo": False, "source": "../scripts/connector.go",
        "source_sha256": digest(source), "helper_sha256": digest(helper), "files": files,
        "tool_contract_sha256": digest(PLUGIN / "scripts/memory-tools.json"),
        "real_macos_execution": False,
    }, indent=2) + "\n")
    print(json.dumps(files))


if __name__ == "__main__":
    main()
