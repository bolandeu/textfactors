"""Other CLIs this one shells out to, and the minimum version of each it needs.

A tool that calls another tool's CLI (instead of importing it as a package
pinned by tag) can't rely on the lock file, so it checks at runtime:

    exe = deps.require_cli("serp", "0.3.0", install_url="https://github.com/bolandeu/serp")
    subprocess.run([exe, "search", ...])

A missing or too old CLI fails with DEPENDENCY_TOO_OLD (exit 1) naming what is
installed, what is needed and how to fix it — not with a confusing error from
deep inside the other tool. See the Standard, Technology.
"""

from __future__ import annotations

import re
import shlex
import shutil
import subprocess
import tomllib
from dataclasses import dataclass
from functools import cache
from importlib import resources
from pathlib import Path

from packaging.version import InvalidVersion, Version

from .._distribution import DIST_NAME
from .errors import DependencyTooOld

VERSION_TIMEOUT = 10.0
_PACKAGE_NAME = __name__.split(".")[0]


@dataclass(frozen=True)
class External:
    """One non-Python dependency, declared in pyproject.toml `[[tool.rb.external]]` (the Standard, Technology)."""

    name: str
    required: bool
    why: str
    min_version: str | None = None
    check: str | None = None  # command printing the version; default "<name> --version"
    detect: bool = True  # False: run in a way the gate can't see (injected runner, absolute path)
    dist: str | None = None  # distribution name for uv tool, if it's one of ours (default rb-<name>)
    url: str | None = None  # its git repo, for a runnable pinned install in DEPENDENCY_TOO_OLD


def _pyproject_text() -> str | None:
    # An installed wheel carries pyproject.toml as <package>/_pyproject.toml
    # (hatch force-include); an editable install reads the checkout's own.
    bundled = resources.files(_PACKAGE_NAME).joinpath("_pyproject.toml")
    if bundled.is_file():
        return bundled.read_text()
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "pyproject.toml"
        if candidate.is_file():
            text = candidate.read_text()
            if tomllib.loads(text).get("project", {}).get("name") == DIST_NAME:
                return text
    return None


@cache
def declared() -> dict[str, External]:
    """The external-dependency registry, by name ({} when there is none)."""
    text = _pyproject_text()
    entries = tomllib.loads(text).get("tool", {}).get("rb", {}).get("external", []) if text else []
    return {
        entry["name"]: External(
            name=entry["name"],
            required=bool(entry.get("required", True)),
            why=entry.get("why", ""),
            min_version=entry.get("min_version"),
            check=entry.get("check"),
            detect=bool(entry.get("detect", True)),
            dist=entry.get("dist"),
            url=entry.get("url"),
        )
        for entry in entries
    }


def _version_in(text: str) -> str | None:
    """The first version-looking token in a `--version` output ("ffmpeg version 6.1.1-3" -> "6.1.1-3" -> 6.1.1)."""
    for token in text.split():
        try:
            Version(token)
            return token.removeprefix("v").removeprefix("V")
        except InvalidVersion:
            if match := re.match(r"v?(\d+(?:\.\d+)+)", token):
                return match.group(1)
    return None


def installed_cli_version(name: str) -> tuple[str | None, str | None]:
    """(path, version) of CLI `name` on PATH; (None, None) when it isn't installed.

    The version comes from the registry's `check` command for `name` if it has
    one, else `<name> --version`.
    """
    exe = shutil.which(name)
    if exe is None:
        return None, None
    spec = declared().get(name)
    argv = shlex.split(spec.check) if spec and spec.check else [name, "--version"]
    try:
        result = subprocess.run(  # noqa: S603 — fixed argv, executable resolved via shutil.which
            [exe, *argv[1:]], capture_output=True, text=True, timeout=VERSION_TIMEOUT, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return exe, None
    return exe, (_version_in(result.stdout + "\n" + result.stderr) if result.returncode == 0 else None)


def doctor_checks() -> list[dict]:
    """One `doctor` check per declared external dependency; a missing optional one doesn't fail."""
    checks: list[dict] = []
    for spec in declared().values():
        exe, version = installed_cli_version(spec.name)
        need = f">= {spec.min_version}" if spec.min_version else "any version"
        if exe is None:
            ok, detail = (
                not spec.required,
                f"not installed ({'required' if spec.required else 'optional'}, {need}): {spec.why}",
            )
        else:
            too_old = bool(spec.min_version and version and Version(version) < Version(spec.min_version))
            ok, detail = not too_old, f"{version or 'version unknown'} ({need}): {spec.why}"
        checks.append({"name": f"external:{spec.name}", "ok": ok, "detail": detail})
    return checks


def require_cli(name: str, min_version: str | None = None, *, install_url: str | None = None) -> str:
    """Path of CLI `name` if it's installed at `min_version` or newer; raise DependencyTooOld otherwise.

    `min_version`, `url` and `dist` default to what `[[tool.rb.external]]`
    in pyproject.toml declares for `name` — declare every external CLI there
    (the gate checks). A repo URL (`install_url` or the entry's `url`, e.g.
    "https://github.com/bolandeu/serp") makes the error's `action` a runnable
    `uv tool install "<dist> @ git+<url>.git@v<min_version>" --force`, where
    `dist` is the entry's `dist` or, for one of our tools, `rb-<name>`; without a URL the action says what to install, never a
    placeholder URL.

    A dev build of the other tool (version `0.0.0…`, no release tag in reach)
    is accepted, the same way this CLI's own `cli.min_version` check treats it.
    """
    spec = declared().get(name)
    min_version = min_version or (spec.min_version if spec else None)
    hint = {
        "install_url": install_url or (spec.url if spec else None),
        "dist": (spec.dist if spec else None) or (f"rb-{name}" if install_url or (spec and spec.url) else None),
    }
    exe, reported = installed_cli_version(name)
    if exe is None:
        raise DependencyTooOld(name, None, min_version, **hint)
    if min_version is None:
        return exe
    try:
        version = Version(reported or "")
    except InvalidVersion:
        raise DependencyTooOld(name, reported or "unknown", min_version, **hint) from None
    if version.release != (0, 0, 0) and version < Version(min_version):
        raise DependencyTooOld(name, reported, min_version, **hint)
    return exe
