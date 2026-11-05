"""Portable, deterministic sync log checkpoints (not a signature scheme)."""
import hashlib
import json

GENESIS = "0" * 64


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      default=str, allow_nan=False)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def operation_digest(body):
    # Omitted optional provenance fields retain the 0.1 operation identity.
    value = dict(body)
    for key in ("session_id", "source_id", "origin"):
        if value.get(key) is None:
            value.pop(key, None)
    return digest(canonical(value))


def chain_hash(previous, sequence, body, fingerprint):
    return digest(canonical([previous, sequence, body, fingerprint]))
