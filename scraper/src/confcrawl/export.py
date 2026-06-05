"""Write the site's data files: per-venue papers + the sidebar manifest."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import VenueConfig
from .models import Paper


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_venue(out_dir: Path, venue: VenueConfig, papers: list[Paper]) -> Path:
    path = out_dir / f"{venue.id}.json"
    write_json(path, [paper.to_dict() for paper in papers])
    return path


def write_manifest(
    out_dir: Path, summaries: list[dict[str, Any]], *, generated_at: str | None = None
) -> Path:
    path = out_dir / "venues.json"
    write_json(
        path,
        {
            "generatedAt": generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "venues": summaries,
        },
    )
    return path
