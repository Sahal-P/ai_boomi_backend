#!/usr/bin/python3 -I
"""Prepare FinBoy-only frontend runtime; never starts services or changes nginx/DNS."""

import hashlib
import os
import pwd
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen


def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def account(name, shell, home):
    try:
        existing = pwd.getpwnam(name)
        if existing.pw_dir != home or existing.pw_shell != shell:
            raise ValueError("account_conflict")
    except KeyError:
        run("useradd", "--system", "--user-group", "--home-dir", home, "--shell", shell, name)
    return pwd.getpwnam(name)


def install(source, target, mode):
    target = Path(target)
    temporary = target.with_name(target.name + ".new")
    shutil.copyfile(source, temporary)
    os.chown(temporary, 0, 0)
    os.chmod(temporary, mode)
    os.replace(temporary, target)


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise ValueError("invalid_invocation")
    source = Path(sys.argv[1]).resolve(strict=True)
    if not source.is_relative_to(Path("/tmp")) or source.stat().st_uid != 0:
        raise ValueError("invalid_staging_directory")
    if shutil.disk_usage("/opt").free < 3 * 1024**3:
        raise ValueError("insufficient_disk")
    for folder in [
        "/opt/finboy-web/releases",
        "/opt/finboy-web/slots",
        "/var/lib/finboy-web/static",
        "/var/cache/finboy-web",
        "/etc/finboy-web",
        "/usr/local/lib/finboy-web",
        "/var/lib/finboy-deploy",
    ]:
        Path(folder).mkdir(parents=True, exist_ok=True, mode=0o755)
    account("finboy-web", "/usr/sbin/nologin", "/var/lib/finboy-web")
    deploy = account("finboy-deploy", "/bin/sh", "/var/lib/finboy-deploy")
    incoming = Path("/var/lib/finboy-deploy/incoming")
    incoming.mkdir(exist_ok=True, mode=0o700)
    os.chown(incoming, deploy.pw_uid, deploy.pw_gid)
    os.chmod(incoming, 0o700)
    node = Path("/opt/finboy-web/node")
    if node.exists():
        result = subprocess.check_output([str(node / "bin/node"), "--version"], text=True).strip()
        if not result.startswith("v24."):
            raise ValueError("node_version_conflict")
    else:
        with urlopen("https://nodejs.org/dist/latest-v24.x/SHASUMS256.txt", timeout=30) as response:
            lines = response.read().decode().splitlines()
        line = next(s for s in lines if re.search(r"node-v24\.\d+\.\d+-linux-x64\.tar\.xz$", s))
        checksum, filename = line.split()
        with tempfile.TemporaryDirectory(dir="/opt/finboy-web") as temporary:
            archive = Path(temporary) / filename
            with (
                urlopen("https://nodejs.org/dist/latest-v24.x/" + filename, timeout=60) as response,
                archive.open("wb") as output,
            ):
                shutil.copyfileobj(response, output)
            if hashlib.sha256(archive.read_bytes()).hexdigest() != checksum:
                raise ValueError("node_checksum_mismatch")
            with tarfile.open(archive) as bundle:
                bundle.extractall(temporary, filter="data")
            shutil.move(Path(temporary) / filename.removesuffix(".tar.xz"), node)
    install(source / "web-control.py", "/usr/local/sbin/finboy-web-control", 0o755)
    install(source / "web-ssh.py", "/usr/local/bin/finboy-web-ssh", 0o755)
    install(source / "web-release.py", "/usr/local/lib/finboy-web/release_tools.py", 0o644)
    install(source / "finboy-web@.service", "/etc/systemd/system/finboy-web@.service", 0o644)
    sudoers = source / "finboy-web-sudoers"
    sudoers.write_text("finboy-deploy ALL=(root) NOPASSWD: /usr/local/sbin/finboy-web-control *\n")
    os.chmod(sudoers, 0o440)
    run("visudo", "-cf", str(sudoers))
    install(sudoers, "/etc/sudoers.d/finboy-web", 0o440)
    run("systemctl", "daemon-reload")
    print("FinBoy web runtime prepared; no service, nginx or DNS changes made.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(str(error) if isinstance(error, ValueError) else "bootstrap_failed", file=sys.stderr)
        sys.exit(1)
