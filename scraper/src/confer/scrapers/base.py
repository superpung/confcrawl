"""The scraper-adapter contract.

Every platform adapter subclasses :class:`Scraper` and returns unified
:class:`~confer.models.Paper` records. Adapters are selected by
``venue.scraper`` via the registry in ``scrapers/__init__.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import VenueConfig
from ..fetcher import Fetcher
from ..models import Paper


class Scraper(ABC):
    #: Registry key; set by subclasses (matches ``venue.scraper``).
    name: str = ""

    def __init__(
        self,
        venue: VenueConfig,
        fetcher: Fetcher,
        *,
        limit: int | None = None,
        workers: int = 6,
    ) -> None:
        self.venue = venue
        self.fetcher = fetcher
        self.limit = limit
        self.workers = max(workers, 1)

    @abstractmethod
    def scrape(self) -> list[Paper]:
        """Fetch + parse the venue and return unified Papers."""
        raise NotImplementedError
