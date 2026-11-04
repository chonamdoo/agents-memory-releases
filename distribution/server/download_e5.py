"""Build-time download of exactly the reviewed E5 assets, with SHA256 checks."""
import hashlib
import json
import os
import ssl
import sys
import urllib.request
from pathlib import Path

target = Path(sys.argv[1])
target.mkdir(parents=True, exist_ok=True)
inputs = json.loads(Path(__file__).with_name("model-sources.json").read_text())
context = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE"))
for item in inputs["model_assets"]:
    path = target / item["local_name"]
    with urllib.request.urlopen(item["source"], timeout=120, context=context) as response, path.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
    if path.stat().st_size != item["bytes"] or hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
        path.unlink()
        raise ValueError("E5 asset integrity mismatch")
print("Reviewed E5 assets ready")
