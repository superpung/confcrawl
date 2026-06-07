"""Locate repo-root directories regardless of the current working directory.

The scraper lives in ``scraper/`` but reads ``config/`` and writes
``web/public/data/`` at the repo root, and caches under ``data/cache/``. These
helpers walk up from the CWD (or this file) to find the repo root so commands
work whether run from the repo root or from ``scraper/``.
"""

from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Return the directory that contains ``config/venues.yaml``.

    Falls back to a directory containing both ``scraper`` and (optionally)
    ``web``, then to the CWD, so the tool degrades gracefully if the seed
    config is missing.
    """
    candidates: list[Path] = []
    if start is not None:
        candidates.append(start)
    candidates.append(Path.cwd())
    candidates.append(Path(__file__).resolve())

    for origin in candidates:
        for directory in [origin, *origin.parents]:
            if (directory / "config" / "venues.yaml").exists():
                return directory
            if (directory / "scraper").is_dir() and (directory / "config").is_dir():
                return directory
    return Path.cwd()


def config_path(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    return root / "config" / "venues.yaml"


def cache_root(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    return root / "data" / "cache"


def site_data_dir(repo_root: Path | None = None) -> Path:
    root = repo_root or find_repo_root()
    return root / "web" / "public" / "data"
