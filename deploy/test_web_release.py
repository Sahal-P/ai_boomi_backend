"""Isolated release safety checks. Never connects to a server or a database."""

import importlib.util
import io
import json
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["activate", "../escape"],
        ["stage", "a" * 40, "bad-checksum"],
        ["shell", "a" * 40],
        ["activate", "a" * 40, "extra"],
        ["drain", "a" * 40, "red"],
    ],
)
def test_activation_rejects_untrusted_arguments_before_any_operations(monkeypatch, arguments):
    control = module("web_control", ROOT / "deploy/web-control.py")
    monkeypatch.setattr(control.sys, "argv", ["web-control", *arguments])
    with pytest.raises(ValueError):
        control.main()


@pytest.mark.parametrize(
    "command",
    [
        "sh",
        "activate $(id)",
        "activate " + "a" * 40 + ";id",
        "upload " + "a" * 40,
        "activate " + "a" * 40 + " " + "b" * 64,
    ],
)
def test_ssh_wrapper_never_executes_arbitrary_commands(monkeypatch, command):
    wrapper = module("web_ssh", ROOT / "deploy/web-ssh.py")
    monkeypatch.setenv("SSH_ORIGINAL_COMMAND", command)
    with pytest.raises(ValueError):
        wrapper.main()


def test_archive_filter_rejects_escape(tmp_path):
    archive = tmp_path / "bad.tar"
    with tarfile.open(archive, "w") as output:
        entry = tarfile.TarInfo("../escaped")
        entry.size = 1
        output.addfile(entry, io.BytesIO(b"x"))
    with tarfile.open(archive) as source, pytest.raises(tarfile.FilterError):
        source.extractall(tmp_path / "target", filter="data")
    assert not (tmp_path / "escaped").exists()


def test_api_digest_changes_only_when_deployed_api_inputs_change(tmp_path):
    release = module("web_release", ROOT / "scripts/web-release.py")
    for folder in ["apps/api/src", "apps/api/alembic", "apps/api/tests"]:
        (tmp_path / folder).mkdir(parents=True)
    (tmp_path / "pyproject.toml").write_text("local fixture")
    (tmp_path / "uv.lock").write_text("local fixture")
    code = tmp_path / "apps/api/src/app.py"
    code.write_text("first")
    initial = release.api_digest(tmp_path)
    (tmp_path / "apps/api/tests/test_app.py").write_text("test only")
    assert release.api_digest(tmp_path) == initial
    code.write_text("second")
    assert release.api_digest(tmp_path) != initial


def test_health_checks_require_the_exact_candidate_revision(monkeypatch):
    control = module("web_control", ROOT / "deploy/web-control.py")
    monkeypatch.setattr(control.time, "sleep", lambda _: None)

    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(
        control,
        "urlopen",
        lambda *_args, **_kw: Response(json.dumps({"status": "ok", "revision": "b" * 40}).encode()),
    )
    with pytest.raises(ValueError, match="candidate_unhealthy"):
        control.healthy(3100, "a" * 40)


def test_activation_restores_previous_upstream_on_nginx_failure(tmp_path, monkeypatch):
    control = module("web_control", ROOT / "deploy/web-control.py")
    root = tmp_path / "releases-root"
    data = tmp_path / "data"
    (root / "releases" / ("a" * 40) / "apps/web/.next/static").mkdir(parents=True)
    data.mkdir()
    (data / "candidate.json").write_text(json.dumps({"revision": "a" * 40, "slot": "green"}))
    upstream = tmp_path / "upstream.conf"
    previous = "server 127.0.0.1:3100;\n"
    upstream.write_text(previous)
    monkeypatch.setattr(control, "ROOT", root)
    monkeypatch.setattr(control, "DATA", data)
    monkeypatch.setattr(control, "UPSTREAM", upstream)
    monkeypatch.setattr(control, "state", lambda: {"active_slot": "blue", "revision": "b" * 40})
    monkeypatch.setattr(control, "metadata", lambda _: None)
    monkeypatch.setattr(control, "healthy", lambda *_: None)

    class Healthy:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(control, "urlopen", lambda *_a, **_kw: Healthy())
    calls = []

    def run(*args):
        calls.append(args)
        if args == ("nginx", "-t") and sum(x == args for x in calls) == 1:
            raise RuntimeError("synthetic nginx failure")

    monkeypatch.setattr(control, "run", run)
    with pytest.raises(RuntimeError):
        control.activate("a" * 40)
    assert upstream.read_text() == previous
    assert ("systemctl", "stop", "finboy-web@green") in calls
    assert not (data / "state.json").exists()


def test_drain_never_stops_the_active_or_new_candidate_slot(tmp_path, monkeypatch):
    control = module("web_control", ROOT / "deploy/web-control.py")
    root, data = tmp_path / "root", tmp_path / "data"
    (root / "releases" / ("a" * 40)).mkdir(parents=True)
    (root / "slots").mkdir()
    (root / "slots" / "blue").symlink_to(root / "releases" / ("a" * 40))
    data.mkdir()
    monkeypatch.setattr(control, "ROOT", root)
    monkeypatch.setattr(control, "DATA", data)
    calls = []
    monkeypatch.setattr(control, "run", lambda *args: calls.append(args))
    monkeypatch.setattr(control, "state", lambda: {"active_slot": "blue"})
    assert control.drain("a" * 40, "blue") == {"drained": False}
    monkeypatch.setattr(control, "state", lambda: {"active_slot": "green"})
    (data / "candidate.json").write_text(json.dumps({"slot": "blue", "revision": "a" * 40}))
    assert control.drain("a" * 40, "blue") == {"drained": False}
    assert not calls
    (data / "candidate.json").unlink()
    assert control.drain("a" * 40, "blue") == {"drained": True}
    assert calls == [("systemctl", "stop", "finboy-web@blue")]


def test_reconciliation_guard_refuses_inconsistent_upstream(tmp_path, monkeypatch):
    control = module("web_control", ROOT / "deploy/web-control.py")
    upstream = tmp_path / "upstream.conf"
    upstream.write_text("server 127.0.0.1:3101;\n")
    monkeypatch.setattr(control, "UPSTREAM", upstream)
    with pytest.raises(ValueError, match="deployment_state_mismatch"):
        control.check_active_upstream({"active_slot": "blue"})


def test_failed_rollback_never_stops_a_potentially_live_candidate(tmp_path, monkeypatch):
    control = module("web_control", ROOT / "deploy/web-control.py")
    root, data = tmp_path / "root", tmp_path / "data"
    (root / "releases" / ("a" * 40) / "apps/web/.next/static").mkdir(parents=True)
    data.mkdir()
    (data / "candidate.json").write_text(json.dumps({"slot": "green", "revision": "a" * 40}))
    upstream = tmp_path / "upstream.conf"
    upstream.write_text("server 127.0.0.1:3100;\n")
    monkeypatch.setattr(control, "ROOT", root)
    monkeypatch.setattr(control, "DATA", data)
    monkeypatch.setattr(control, "UPSTREAM", upstream)
    monkeypatch.setattr(control, "state", lambda: {"active_slot": "blue", "revision": "b" * 40})
    monkeypatch.setattr(control, "metadata", lambda _: None)
    monkeypatch.setattr(control, "healthy", lambda *_: None)

    class Healthy:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(control, "urlopen", lambda *_a, **_kw: Healthy())
    calls = []

    def run(*args):
        calls.append(args)
        if args == ("nginx", "-t"):
            raise RuntimeError("synthetic nginx failure")

    monkeypatch.setattr(control, "run", run)
    with pytest.raises(ValueError, match="rollback_incomplete"):
        control.activate("a" * 40)
    assert (data / "needs-reconciliation").exists()
    assert ("systemctl", "stop", "finboy-web@green") not in calls
    with pytest.raises(ValueError, match="deployment_reconciliation_required"):
        control.check_active_upstream({"active_slot": "blue"})


def test_successful_activation_enables_new_slot_and_schedules_safe_drain(tmp_path, monkeypatch):
    control = module("web_control", ROOT / "deploy/web-control.py")
    root, data = tmp_path / "root", tmp_path / "data"
    static = root / "releases" / ("a" * 40) / "apps/web/.next/static"
    static.mkdir(parents=True)
    (static / "chunk.js").write_text("synthetic")
    data.mkdir()
    (data / "candidate.json").write_text(json.dumps({"slot": "green", "revision": "a" * 40}))
    state = data / "state.json"
    state.write_text(json.dumps({"active_slot": "blue", "revision": "b" * 40, "history": []}))
    upstream = tmp_path / "upstream.conf"
    upstream.write_text("server 127.0.0.1:3100;\n")
    monkeypatch.setattr(control, "ROOT", root)
    monkeypatch.setattr(control, "DATA", data)
    monkeypatch.setattr(control, "STATE", state)
    monkeypatch.setattr(control, "UPSTREAM", upstream)
    monkeypatch.setattr(control, "metadata", lambda _: None)
    monkeypatch.setattr(control, "healthy", lambda *_: None)

    class Healthy:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    monkeypatch.setattr(control, "urlopen", lambda *_a, **_kw: Healthy())

    def curl(args, **_kwargs):
        path = args[-1]
        if path.endswith("/healthz"):
            return json.dumps({"status": "ok", "revision": "a" * 40}).encode()
        return b"401" if path.endswith("/money/summary") else b"200"

    monkeypatch.setattr(control.subprocess, "check_output", curl)
    monkeypatch.setattr(
        control.time, "sleep", lambda _: pytest.fail("activation blocked for drain")
    )
    calls = []
    monkeypatch.setattr(control, "run", lambda *args: calls.append(args))
    assert control.activate("a" * 40) == {"active": "a" * 40, "slot": "green"}
    assert ("systemctl", "enable", "finboy-web@green") in calls
    assert ("systemctl", "disable", "finboy-web@blue") in calls
    assert ("systemctl", "stop", "finboy-web@blue") not in calls
    assert any(call[0] == "systemd-run" and "--on-active=120s" in call for call in calls)
    assert json.loads(state.read_text())["drain_slot"] == "blue"
