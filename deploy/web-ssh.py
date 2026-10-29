#!/usr/bin/python3 -I
"""Forced SSH command for the deployment account; no shell or forwarding permitted."""

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def main():
    command = os.environ.get("SSH_ORIGINAL_COMMAND", "")
    match = re.fullmatch(r"(upload|stage|activate) ([a-f0-9]{40})(?: ([a-f0-9]{64}))?", command)
    if not match:
        raise ValueError("invalid_command")
    action, revision, checksum = match.groups()
    if (action in {"upload", "stage"}) != bool(checksum):
        raise ValueError("invalid_arguments")
    if action != "upload":
        args = ["/usr/bin/sudo", "-n", "/usr/local/sbin/finboy-web-control", action, revision]
        if checksum:
            args.append(checksum)
        return subprocess.call(args)
    folder = Path("/var/lib/finboy-deploy/incoming")
    temporary = folder / f"{revision}.part"
    target = folder / f"{revision}.tar.gz"
    digest, size = hashlib.sha256(), 0
    try:
        with os.fdopen(
            os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"
        ) as output:
            while chunk := sys.stdin.buffer.read(1024 * 1024):
                size += len(chunk)
                if size > 200 * 1024**2:
                    raise ValueError("archive_too_large")
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != checksum:
            raise ValueError("checksum_mismatch")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"uploaded": revision}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        print('{"error":"upload_failed"}')
        sys.exit(1)
