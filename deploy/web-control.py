#!/usr/bin/python3 -I
"""Root-owned, fixed-purpose frontend activation. No API restart or schema mutation."""

import fcntl
import hashlib
import importlib.util
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import Path
from urllib.request import urlopen

ROOT = Path("/opt/finboy-web")
DATA = Path("/var/lib/finboy-web")
STATE = DATA / "state.json"
UPSTREAM = Path("/etc/nginx/snippets/finboy-web-upstream.conf")
PORTS = {"blue": 3100, "green": 3101}


def run(*args):
    subprocess.run(
        args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=190
    )


def atomic(path, content):
    temporary = path.with_name(path.name + ".new")
    temporary.write_text(content)
    os.chmod(temporary, 0o644)
    os.replace(temporary, path)


def state():
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def metadata(revision):
    value = json.loads((ROOT / "releases" / revision / "release.json").read_text())
    if value["revision"] != revision or value["node_major"] != 24:
        raise ValueError("invalid_release")
    spec = importlib.util.spec_from_file_location(
        "release_tools", "/usr/local/lib/finboy-web/release_tools.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.api_digest(Path("/opt/finboy/current").resolve()) != value["api_digest"]:
        raise ValueError("api_release_required")
    return value


def healthy(port, revision):
    for _ in range(30):
        try:
            with urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as response:
                body = json.load(response)
                if body == {"status": "ok", "revision": revision}:
                    return
        except Exception:
            pass
        time.sleep(1)
    raise ValueError("candidate_unhealthy")


def link(path, target):
    temporary = path.with_name(path.name + ".new")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    os.replace(temporary, path)


def check_active_upstream(current):
    if (DATA / "needs-reconciliation").exists():
        raise ValueError("deployment_reconciliation_required")
    slot = current.get("active_slot")
    if slot and (
        not UPSTREAM.exists() or UPSTREAM.read_text().strip() != f"server 127.0.0.1:{PORTS[slot]};"
    ):
        raise ValueError("deployment_state_mismatch")


def wait_for_slot(current, slot):
    if current.get("drain_slot") != slot:
        return
    delay = max(0, current.get("drain_until", 0) - time.time())
    if delay:
        time.sleep(min(delay, 120))
    if current.get("drain_until", 0) > time.time():
        raise ValueError("slot_draining")


def drain(revision, slot):
    current = state()
    if current.get("active_slot") == slot:
        return {"drained": False}
    candidate_path = DATA / "candidate.json"
    if candidate_path.exists():
        candidate = json.loads(candidate_path.read_text())
        if candidate.get("slot") == slot and candidate.get("revision") == revision:
            return {"drained": False}
    target = ROOT / "slots" / slot
    if target.is_symlink() and target.resolve() == ROOT / "releases" / revision:
        run("systemctl", "stop", f"finboy-web@{slot}")
        return {"drained": True}
    return {"drained": False}


def stage(revision, checksum):
    if shutil.disk_usage(ROOT).free < 3 * 1024**3:
        raise ValueError("insufficient_disk")
    incoming = Path("/var/lib/finboy-deploy/incoming") / f"{revision}.tar.gz"
    destination = ROOT / "releases" / revision
    created = False
    # Copy to a root-only directory before validating; upload users cannot change validated bytes.
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        private = Path(temporary) / "release.tar.gz"
        with (
            os.fdopen(os.open(incoming, os.O_RDONLY | os.O_NOFOLLOW), "rb") as source,
            private.open("wb") as output,
        ):
            shutil.copyfileobj(source, output)
        if private.stat().st_size > 200 * 1024**2:
            raise ValueError("archive_too_large")
        if hashlib.sha256(private.read_bytes()).hexdigest() != checksum:
            raise ValueError("checksum_mismatch")
        current = state()
        if current.get("revision") == revision:
            metadata(revision)
            healthy(PORTS[current["active_slot"]], revision)
            incoming.unlink(missing_ok=True)
            return {"staged": revision, "slot": current["active_slot"], "already_active": True}
        unpacked = Path(temporary) / "unpacked"
        unpacked.mkdir()
        with tarfile.open(private) as bundle:
            members = bundle.getmembers()
            if sum(item.size for item in members) > 1024**3 or len(members) > 100000:
                raise ValueError("expanded_archive_too_large")
            if any(
                Path(item.name).name == ".env" or Path(item.name).name.startswith(".env.")
                for item in members
            ):
                raise ValueError("environment_in_archive")
            bundle.extractall(unpacked, filter="data")
        if destination.exists():
            recorded = destination / ".archive.sha256"
            if not recorded.is_file() or recorded.read_text().strip() != checksum:
                raise ValueError("release_already_exists")
        else:
            (unpacked / ".archive.sha256").write_text(checksum + "\n")
            shutil.move(unpacked, destination)
            created = True
    try:
        metadata(revision)
    except Exception:
        if created:
            shutil.rmtree(destination)
        raise
    # Uploaded archive permissions cannot grant the web process permission to edit executable code.
    for directory, _dirs, files in os.walk(destination):
        os.chown(directory, 0, 0)
        os.chmod(directory, 0o755)
        for name in files:
            file = Path(directory) / name
            if not file.is_symlink():
                os.chown(file, 0, 0)
                os.chmod(file, 0o644)
    cache = Path("/var/cache/finboy-web") / revision
    cache.mkdir(parents=True, exist_ok=True)
    account = pwd.getpwnam("finboy-web")
    os.chown(cache, account.pw_uid, account.pw_gid)
    next_cache = destination / "apps/web/.next/cache"
    if next_cache.is_dir() and not next_cache.is_symlink():
        shutil.rmtree(next_cache)
    next_cache.unlink(missing_ok=True)
    next_cache.symlink_to(cache)
    current = state()
    check_active_upstream(current)
    slot = "green" if current.get("active_slot") == "blue" else "blue"
    wait_for_slot(current, slot)
    run("systemctl", "stop", f"finboy-web@{slot}")
    link(ROOT / "slots" / slot, destination)
    atomic(
        Path("/etc/finboy-web") / f"{slot}.env",
        f"PORT={PORTS[slot]}\nFINBOY_RELEASE_SHA={revision}\n",
    )
    (DATA / "candidate.json").unlink(missing_ok=True)
    try:
        run("systemctl", "start", f"finboy-web@{slot}")
        healthy(PORTS[slot], revision)
    except Exception:
        run("systemctl", "stop", f"finboy-web@{slot}")
        raise
    atomic(DATA / "candidate.json", json.dumps({"slot": slot, "revision": revision}))
    incoming.unlink(missing_ok=True)
    return {"staged": revision, "slot": slot, "port": PORTS[slot]}


def activate(revision):
    current = state()
    check_active_upstream(current)
    if current.get("revision") == revision:
        metadata(revision)
        healthy(PORTS[current["active_slot"]], revision)
        return {"active": revision, "slot": current["active_slot"], "already_active": True}
    candidate = json.loads((DATA / "candidate.json").read_text())
    if candidate["revision"] != revision:
        raise ValueError("candidate_mismatch")
    metadata(revision)
    slot = candidate["slot"]
    healthy(PORTS[slot], revision)
    with urlopen("http://127.0.0.1:8020/api/v1/health", timeout=5) as response:
        if response.status != 200:
            raise ValueError("api_unhealthy")
    # Merge immutable assets, rejecting same-path/different-byte collisions.
    static = ROOT / "releases" / revision / "apps/web/.next/static"
    for source in static.rglob("*"):
        if not source.is_file():
            continue
        target = DATA / "static" / source.relative_to(static)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise ValueError("static_asset_collision")
        if not target.exists():
            shutil.copyfile(source, target)
            os.chmod(target, 0o644)
    old = UPSTREAM.read_text() if UPSTREAM.exists() else None
    enabled_new = False
    try:
        # During a crash both slots can start, but the nginx-selected slot remains available.
        run("systemctl", "enable", f"finboy-web@{slot}")
        enabled_new = True
        atomic(UPSTREAM, f"server 127.0.0.1:{PORTS[slot]};\n")
        run("nginx", "-t")
        run("systemctl", "reload", "nginx")
        # Exercise the actual nginx route and its hostname, without DNS propagation dependencies.
        result = subprocess.check_output(
            [
                "curl",
                "--fail",
                "--silent",
                "--show-error",
                "--resolve",
                "finboy.io:443:127.0.0.1",
                "--max-time",
                "10",
                "https://finboy.io/healthz",
            ],
            stderr=subprocess.DEVNULL,
        )
        if json.loads(result) != {"status": "ok", "revision": revision}:
            raise ValueError("public_health_mismatch")
        for path, expected in [
            ("/api/v1/health", "200"),
            ("/api/v1/money/summary", "401"),
            ("/brand/finboy-mark.svg", "200"),
        ]:
            status = subprocess.check_output(
                [
                    "curl",
                    "--silent",
                    "--show-error",
                    "--resolve",
                    "finboy.io:443:127.0.0.1",
                    "--max-time",
                    "10",
                    "--output",
                    "/dev/null",
                    "--write-out",
                    "%{http_code}",
                    f"https://finboy.io{path}",
                ],
                stderr=subprocess.DEVNULL,
            ).decode()
            if status != expected:
                raise ValueError("public_smoke_failed")
        if current.get("active_slot") and current["active_slot"] != slot:
            run("systemctl", "disable", f"finboy-web@{current['active_slot']}")
    except Exception:
        try:
            if old is None:
                raise ValueError("previous_upstream_missing")
            atomic(UPSTREAM, old)
            run("nginx", "-t")
            run("systemctl", "reload", "nginx")
            if enabled_new:
                run("systemctl", "disable", f"finboy-web@{slot}")
            if current.get("active_slot"):
                run("systemctl", "enable", f"finboy-web@{current['active_slot']}")
            run("systemctl", "stop", f"finboy-web@{slot}")
        except Exception:
            # If nginx cannot restore the prior route, do not stop either slot blindly.
            atomic(DATA / "needs-reconciliation", "manual reconciliation required\n")
            raise ValueError("rollback_incomplete") from None
        raise
    history = list(dict.fromkeys([revision, current.get("revision"), *current.get("history", [])]))
    history = [item for item in history if item][:3]
    updated = {"active_slot": slot, "revision": revision, "history": history}
    if current.get("active_slot") and current["active_slot"] != slot:
        updated.update({"drain_slot": current["active_slot"], "drain_until": time.time() + 120})
    atomic(STATE, json.dumps(updated))
    # A transient timer drains old workers without holding the release job open.
    if current.get("active_slot") and current["active_slot"] != slot:
        try:
            run(
                "systemd-run",
                "--quiet",
                "--collect",
                f"--unit=finboy-web-drain-{uuid.uuid4().hex[:12]}",
                "--on-active=120s",
                "/usr/local/sbin/finboy-web-control",
                "drain",
                current["revision"],
                current["active_slot"],
            )
        except Exception:
            # If the timer cannot be installed, keep the lock while draining synchronously.
            time.sleep(120)
            run("systemctl", "stop", f"finboy-web@{current['active_slot']}")
    for path in (ROOT / "releases").iterdir():
        if path.is_dir() and re.fullmatch("[a-f0-9]{40}", path.name) and path.name not in history:
            shutil.rmtree(path)
            shutil.rmtree(Path("/var/cache/finboy-web") / path.name, ignore_errors=True)
    referenced = set()
    for item in history:
        folder = ROOT / "releases" / item / "apps/web/.next/static"
        referenced.update(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())
    for file in (DATA / "static").rglob("*"):
        if file.is_file() and str(file.relative_to(DATA / "static")) not in referenced:
            file.unlink()
    return {"active": revision, "slot": slot}


def main():
    args = sys.argv[1:]
    if not args or args[0] not in {"stage", "activate", "rollback", "drain"}:
        raise ValueError("invalid_command")
    command = args[0]
    if len(args) != (3 if command in {"stage", "drain"} else 2) or not re.fullmatch(
        "[a-f0-9]{40}", args[1]
    ):
        raise ValueError("invalid_arguments")
    if command == "stage" and not re.fullmatch("[a-f0-9]{64}", args[2]):
        raise ValueError("invalid_checksum")
    if command == "drain" and args[2] not in PORTS:
        raise ValueError("invalid_slot")
    with Path("/run/lock/finboy-web.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if command == "stage":
            result = stage(args[1], args[2])
        elif command == "drain":
            result = drain(args[1], args[2])
        elif command == "rollback":
            current = state()
            check_active_upstream(current)
            if args[1] not in current.get("history", []):
                raise ValueError("unknown_rollback")
            slot = "green" if current["active_slot"] == "blue" else "blue"
            wait_for_slot(current, slot)
            metadata(args[1])
            run("systemctl", "stop", f"finboy-web@{slot}")
            link(ROOT / "slots" / slot, ROOT / "releases" / args[1])
            atomic(
                Path("/etc/finboy-web") / f"{slot}.env",
                f"PORT={PORTS[slot]}\nFINBOY_RELEASE_SHA={args[1]}\n",
            )
            run("systemctl", "start", f"finboy-web@{slot}")
            atomic(DATA / "candidate.json", json.dumps({"slot": slot, "revision": args[1]}))
            result = activate(args[1])
        else:
            result = activate(args[1])
        print(json.dumps(result))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        code = str(error) if isinstance(error, ValueError) else "operation_failed"
        print(json.dumps({"error": code if re.fullmatch("[a-z_]+", code) else "operation_failed"}))
        sys.exit(1)
