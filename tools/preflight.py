#!/usr/bin/env python3
"""Safe, dependency-light runtime preflight checks for MooSight.

The preflight intentionally avoids importing the SpiderFoot runtime so that it
can diagnose common installation problems without triggering application-wide
side effects. It is suitable for launch scripts, support diagnostics, and CI.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import socket
import sqlite3
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5001
MIN_PYTHON = (3, 10)


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    message: str
    required: bool = True


REQUIRED_FILES = (
    "sf.py",
    "sflib.py",
    "requirements.txt",
    "modules",
    "spiderfoot",
    "spiderfoot/templates",
    "spiderfoot/static",
)


def check_python(version_info=None) -> Check:
    version = tuple((version_info or sys.version_info)[:3])
    ok = version >= MIN_PYTHON
    return Check(
        name="python",
        ok=ok,
        message=(
            f"Python {version[0]}.{version[1]}.{version[2]} detected; "
            f"minimum supported for this MooSight branch is {MIN_PYTHON[0]}.{MIN_PYTHON[1]}."
        ),
    )


def check_repository(root: Path = ROOT) -> Check:
    missing = [entry for entry in REQUIRED_FILES if not (root / entry).exists()]
    if missing:
        return Check(
            name="repository",
            ok=False,
            message="Missing required repository paths: " + ", ".join(missing),
        )
    return Check("repository", True, "Required MooSight repository files are present.")


def _requirement_name(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("#") or line.startswith(("-r", "--", "git+", "http://", "https://")):
        return None
    for marker in (";", "[", "<", ">", "=", "!", "~"):
        line = line.split(marker, 1)[0]
    name = line.strip()
    return name or None


def requirement_names(path: Path) -> list[str]:
    if not path.exists():
        return []
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        name = _requirement_name(line)
        if name:
            names.append(name)
    return sorted(set(names), key=str.lower)


def check_dependencies(root: Path = ROOT) -> Check:
    req_path = root / "requirements.txt"
    names = requirement_names(req_path)
    if not names:
        return Check("dependencies", False, "No runtime dependencies could be read from requirements.txt.")

    missing = []
    for name in names:
        try:
            importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            missing.append(name)

    if missing:
        preview = ", ".join(missing[:10])
        if len(missing) > 10:
            preview += f" (+{len(missing) - 10} more)"
        return Check("dependencies", False, f"Missing installed packages: {preview}")
    return Check("dependencies", True, f"All {len(names)} declared runtime packages are installed.")


def check_port(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> Check:
    if not 1 <= int(port) <= 65535:
        return Check("port", False, f"Invalid TCP port: {port}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(0.5)
        result = sock.connect_ex((host, int(port)))
    except OSError as exc:
        return Check("port", False, f"Could not test {host}:{port}: {type(exc).__name__}: {exc}")
    finally:
        sock.close()

    if result == 0:
        return Check("port", False, f"{host}:{port} is already in use.")
    return Check("port", True, f"{host}:{port} is available.")


def check_writable_paths(root: Path = ROOT) -> Check:
    failures = []
    for relative in ("cache", "log"):
        path = root / relative
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".moosight-write-test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            failures.append(f"{relative}: {type(exc).__name__}")
    if failures:
        return Check("writable_paths", False, "Cannot write runtime directories: " + ", ".join(failures))
    return Check("writable_paths", True, "Runtime cache and log directories are writable.")


def check_database(root: Path = ROOT) -> Check:
    db_path = root / "spiderfoot.db"
    if not db_path.exists():
        return Check("database", True, "No existing database found; MooSight can create one on first run.", required=False)

    try:
        connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True, timeout=2)
        try:
            row = connection.execute("PRAGMA quick_check").fetchone()
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return Check("database", False, f"Existing SQLite database could not be checked: {exc}")

    if not row or row[0] != "ok":
        return Check("database", False, f"SQLite quick_check reported: {row[0] if row else 'no result'}")
    return Check("database", True, "Existing SQLite database passed PRAGMA quick_check.")


def run_checks(root: Path = ROOT, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> list[Check]:
    return [
        check_python(),
        check_repository(root),
        check_dependencies(root),
        check_writable_paths(root),
        check_database(root),
        check_port(host, port),
    ]


def exit_code(checks: Iterable[Check]) -> int:
    return 1 if any(check.required and not check.ok for check in checks) else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    checks = run_checks(args.root.resolve(), args.host, args.port)
    if args.as_json:
        print(json.dumps([asdict(item) for item in checks], indent=2))
    else:
        for item in checks:
            marker = "OK" if item.ok else ("WARN" if not item.required else "FAIL")
            print(f"[{marker}] {item.name}: {item.message}")

    return exit_code(checks)


if __name__ == "__main__":
    raise SystemExit(main())
