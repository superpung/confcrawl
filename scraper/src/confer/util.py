"""Small HTML/text helpers shared across adapters."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from bs4 import Tag


def clean_text(node: Tag | None) -> str:
    if node is None:
        return ""
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def split_classes(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return value.split()
    return list(value)


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def parse_query(href: str) -> dict[str, str]:
    query = parse_qs(urlparse(href.replace("&amp;", "&")).query)
    return {key: values[0] for key, values in query.items() if values}


def cache_name_for_url(url: str, suffix: str = ".html") -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    parsed = urlparse(url)
    safe_path = re.sub(r"[^A-Za-z0-9_.-]+", "_", parsed.path.strip("/") or "home")
    return f"{safe_path}_{digest}{suffix}"


def safe_slug(value: str, fallback: str = "none") -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value or fallback)
