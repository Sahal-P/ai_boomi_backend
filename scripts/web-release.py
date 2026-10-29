"""Package a standalone web build; never include environment files or API secrets."""

import argparse
import hashlib
import json
import re
import shutil
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def api_digest(root: Path) -> str:
    files = [root / "pyproject.toml", root / "uv.lock"]
    for folder in ["apps/api/src", "apps/api/alembic"]:
        files.extend(
            p
            for p in (root / folder).rglob("*")
            if p.is_file() and "__pycache__" not in p.parts and p.suffix != ".pyc"
        )
    digest = hashlib.sha256()
    for file in sorted(files):
        digest.update(str(file.relative_to(root)).encode() + b"\0")
        digest.update(hashlib.sha256(file.read_bytes()).digest())
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("revision")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if not re.fullmatch("[a-f0-9]{40}", args.revision):
        parser.error("a full commit revision is required")
    standalone = ROOT / "apps/web/.next/standalone"
    if not (standalone / "apps/web/server.js").is_file():
        parser.error("build the standalone application first")
    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="finboy-web-") as temporary:
        stage = Path(temporary) / "release"
        shutil.copytree(
            standalone,
            stage,
            symlinks=True,
            ignore=shutil.ignore_patterns(".env", ".env.*", "__pycache__"),
        )
        shutil.copytree(ROOT / "apps/web/public", stage / "apps/web/public")
        shutil.copytree(ROOT / "apps/web/.next/static", stage / "apps/web/.next/static")
        metadata = {
            "revision": args.revision,
            "api_digest": api_digest(ROOT),
            "node_major": 24,
            "entrypoint": "apps/web/server.js",
        }
        (stage / "release.json").write_text(json.dumps(metadata) + "\n")
        # Environment files can also enter through traced symlink targets.
        for file in stage.rglob("*"):
            if file.name == ".env" or file.name.startswith(".env."):
                raise RuntimeError("environment file found in release")
            if file.is_symlink() and not file.resolve().is_relative_to(stage.resolve()):
                raise RuntimeError("release symlink escapes the archive")
        archive = args.output / f"{args.revision}.tar.gz"
        with tarfile.open(archive, "w:gz") as bundle:
            for file in sorted(stage.iterdir()):
                bundle.add(file, arcname=file.name)
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        (args.output / f"{args.revision}.sha256").write_text(f"{checksum}  {archive.name}\n")
        print(
            json.dumps(
                {"revision": args.revision, "sha256": checksum, "bytes": archive.stat().st_size}
            )
        )


if __name__ == "__main__":
    main()
