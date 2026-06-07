"""The unified paper schema shared by every scraper adapter and the site.

Field names are snake_case in Python; :meth:`Paper.to_dict` emits the camelCase
keys the Astro site consumes (see AGENTS.md "Unified Paper schema").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Paper:
    id: str
    title: str = ""
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    author_institutions: str = ""
    tracks: list[str] = field(default_factory=list)
    event_type: str = ""
    session_titles: list[str] = field(default_factory=list)
    sessions: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": list(self.authors),
            "authorInstitutions": self.author_institutions,
            "tracks": list(self.tracks),
            "eventType": self.event_type,
            "sessionTitles": list(self.session_titles),
            "sessions": list(self.sessions),
            "dates": list(self.dates),
            "locations": list(self.locations),
            "urls": list(self.urls),
        }
        if self.extra:
            data["extra"] = self.extra
        return data
