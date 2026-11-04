"""Digest-pinned local E5. No generation model or runtime model downloads."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from threading import Lock


class E5:
    def __init__(self, directory: Path, manifest: Path):
        import numpy as np
        import onnxruntime as ort
        from tokenizers import Tokenizer

        expected = json.loads(manifest.read_text())
        for name, digest in expected.items():
            path = directory / name
            if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError("E5 model checksum mismatch")
        self.np = np
        self.tokenizer = Tokenizer.from_file(str(directory / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=512)
        self.tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        self.session = ort.InferenceSession(str(directory / "model.onnx"), options,
                                           providers=["CPUExecutionProvider"])
        self.lock = Lock()

    def encode(self, text: str, *, query: bool = False) -> list[float]:
        with self.lock:
            np = self.np
            encoded = self.tokenizer.encode(("query: " if query else "passage: ") + text)
            values = {"input_ids": np.array([encoded.ids], dtype=np.int64),
                      "attention_mask": np.array([encoded.attention_mask], dtype=np.int64),
                      "token_type_ids": np.array([encoded.type_ids], dtype=np.int64)}
            values = {item.name: values[item.name] for item in self.session.get_inputs()}
            hidden = self.session.run(None, values)[0]
            mask = np.array(encoded.attention_mask)[None, :, None]
            vector = ((hidden * mask).sum(axis=1) / mask.sum(axis=1))[0]
            vector = vector / max(float(np.linalg.norm(vector)), 1e-12)
            if len(vector) != 384 or not all(math.isfinite(float(x)) for x in vector):
                raise ValueError("Invalid E5 embedding")
            return [float(x) for x in vector]
