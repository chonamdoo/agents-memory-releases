#!/usr/bin/env python3
"""Check an extension archive against the actual PostgreSQL build's DLSUFFIX contract."""
import argparse
import hashlib
import json
import re
import struct
import tarfile
from pathlib import Path


def verify(postgres, vector, system):
    with tarfile.open(postgres) as source:
        headers = [item for item in source.getmembers() if item.name.endswith("/include/server/pg_config.h")]
        if len(headers) != 1 or not headers[0].isfile():
            raise ValueError("PostgreSQL archive must contain exactly one server pg_config.h")
        header = source.extractfile(headers[0]).read()
    match = re.search(rb'^#define\s+DLSUFFIX\s+"([^"]+)"', header, re.MULTILINE)
    if match is None:
        raise ValueError("PostgreSQL did not declare DLSUFFIX")
    suffix = match[1].decode("ascii")
    expected = {"Darwin": ".dylib", "Linux": ".so"}[system]
    if suffix != expected:
        raise ValueError("PostgreSQL DLSUFFIX differs from the supported platform contract")
    name = "lib/vector" + suffix
    with tarfile.open(vector) as source:
        members = {item.name: item for item in source.getmembers()}
        if name not in members or not members[name].isfile():
            raise ValueError("PostgreSQL requires " + name + "; extension archive does not provide it")
        module = source.extractfile(members[name]).read()
        control = source.extractfile("share/extension/vector.control").read()
        if not re.search(rb"module_pathname\s*=\s*'\$libdir/vector'", control):
            raise ValueError("Unexpected vector module path in extension control file")
    if system == "Darwin":
        magic, cpu, _, kind = struct.unpack_from("<IIII", module)
        if (magic, cpu, kind) != (0xfeedfacf, 0x100000c, 6):
            raise ValueError("Expected an arm64 Mach-O shared library")
    elif module[:4] != b"\x7fELF" or struct.unpack_from("<HH", module, 16) != (3, 62):
        raise ValueError("Expected an x86_64 ELF shared library")
    return {"platform": system, "postgres_dlsuffix": suffix, "module": name,
            "module_sha256": hashlib.sha256(module).hexdigest(),
            "postgres_header_sha256": hashlib.sha256(header).hexdigest(),
            "lookup_contract": "passed", "native_execution": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--postgres", type=Path, required=True)
    parser.add_argument("--vector", type=Path, required=True)
    parser.add_argument("--system", choices=("Darwin", "Linux"), required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(verify(args.postgres, args.vector, args.system), indent=2))
    except (ValueError, KeyError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
