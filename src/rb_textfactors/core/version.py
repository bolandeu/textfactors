"""The installed version, summary and command name of this package, read from its distribution metadata, and the probes
for optional modules.
"""

from __future__ import annotations

import functools
import importlib
import importlib.util
from importlib.metadata import Distribution, PackageNotFoundError, distribution
from types import ModuleType

from .._distribution import DIST_NAME, DIST_NAME_LEGACY

_PACKAGE_NAME = __name__.split(".")[0]

DEV_VERSION = "0.0.0-dev"


def _distribution() -> Distribution:
    """This package's installed distribution: by DIST_NAME, else by DIST_NAME_LEGACY (a rename in progress)."""
    for name in (DIST_NAME, DIST_NAME_LEGACY):
        if name:
            try:
                return distribution(name)
            except PackageNotFoundError:
                continue
    raise PackageNotFoundError(DIST_NAME)


def module_exists(name: str) -> bool:
    """Whether module `name` (dotted) can be imported, without importing it.

    For optional parts a generated CLI may not have (`credentials.manager`,
    `commands.login`): probe the module, never its package — a directory
    left holding only `__pycache__` still imports as a namespace package.
    """
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:  # a parent package is missing entirely
        return False


def optional_module(name: str) -> ModuleType | None:
    """Module `name` (dotted) of an optional part, or None when the package was generated without that part."""
    return importlib.import_module(name) if module_exists(name) else None


@functools.cache
def cli_name() -> str:
    """The command users type: this package's console script (`[project.scripts]`, copier's `cli_name`).

    It may differ from the Python package name (command `sitemap-xml`,
    package `rb_sitemap_xml`), so anything that names the command — error
    actions, `{cli}` in docstrings, `auth status`'s `tool` — uses this, while
    the keychain service, env var prefix and `.<package>/` project dir keep
    the package name. A bare source run (nothing installed) falls back to it.
    The distribution (`DIST_NAME`, `rb-<slug>`) is a third,
    separate name: what `uv tool install/upgrade` and dependencies use.
    """
    try:
        entry_points = _distribution().entry_points
    except PackageNotFoundError:
        return _PACKAGE_NAME
    for entry_point in entry_points:
        if entry_point.group == "console_scripts" and entry_point.value.startswith(f"{_PACKAGE_NAME}."):
            return entry_point.name
    return _PACKAGE_NAME


def package_summary() -> str:
    """The one-line `description` from pyproject.toml, as installed."""
    try:
        return _distribution().metadata["Summary"] or ""
    except PackageNotFoundError:
        return ""


def installed_version() -> str | None:
    """Version of this package as installed, or None when it isn't installed at all.

    None only happens when the source tree is run without any install (not
    even `uv sync`'s editable one) — callers treat it as "dev build" and skip
    anything that would compare versions.
    """
    try:
        return _distribution().version
    except PackageNotFoundError:
        return None
