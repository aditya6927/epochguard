"""Check exact LF schema bytes, optionally against a Git revision; no network."""

import argparse
import hashlib
from pathlib import Path
import subprocess

SCHEMAS = {
    "schema-004a.v1.json": "4844a67557f27a96feca2a439d68cefd1a70724010f923bf3f135a45158d4986",
    "schema-004a.identification.v1.json": "4514b8bc30d2acf9e7ac1f928cb28180db499e52297e26b4cc11d85b454e526a",
}


def check_bytes(name, data):
    if b"\r" in data or not data.endswith(b"\n"):
        raise ValueError(f"{name}: expected LF bytes and final newline")
    if hashlib.sha256(data).hexdigest() != SCHEMAS[name]:
        raise ValueError(f"{name}: schema hash mismatch")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--git-ref", help="also compare exact bytes with this local Git revision")
    args = parser.parse_args()
    package = Path(__file__).resolve().parents[1]
    repository = package.parents[1]
    for name, expected in SCHEMAS.items():
        data = (package / name).read_bytes()
        check_bytes(name, data)
        if args.git_ref:
            relative = (package / name).relative_to(repository).as_posix()
            blob = subprocess.check_output(["git", "show", f"{args.git_ref}:{relative}"], cwd=repository)
            check_bytes(name, blob)
            if blob != data:
                raise ValueError(f"{name}: Git bytes differ")
        print(f"{name} SHA-256 {expected} LF OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
