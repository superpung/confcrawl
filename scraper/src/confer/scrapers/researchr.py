"""Adapter for Researchr conference programs (``conf.researchr.org``).

Source-specific options:

    program_url:         the Researchr program page (required)
    context:             Researchr context id, inferred from program_url when absent
    include_tracks:      track display names to keep (optional)
    include_event_types: event type labels to keep (optional)
    exclude_event_types: event type labels to drop (optional)
    fetch_details:       fetch event detail modals for abstracts (default true)
    require_authors:     skip records without parsed authors (default false)
"""

from __future__ import annotations

import json
import re
import sys
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

from ..config import VenueConfig
from ..fetcher import Fetcher
from ..models import Paper
from ..util import clean_text, safe_slug, unique_preserve_order
from .base import Scraper


DURATION_RE = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?$")


@dataclass
class ResearchrModalConfig:
    action_url: str
    action_name: str
    context: str
    event_input_name: str
    form_name: str = ""
    placeholder_id: str = "event-modal-loader"


@dataclass
class ResearchrOccurrence:
    event_id: str
    slot_id: str
    title: str
    event_type: str
    tracks: list[str]
    facet_tracks: list[str]
    authors: list[str]
    author_institutions: str
    session_id: str
    session_title: str
    date: str
    location: str
    urls: list[str] = field(default_factory=list)


@dataclass
class ResearchrEvent:
    event_id: str
    title: str
    event_types: list[str]
    tracks: list[str]
    facet_tracks: list[str]
    authors: list[str]
    author_institutions: str
    slot_ids: list[str]
    session_ids: list[str]
    session_titles: list[str]
    dates: list[str]
    locations: list[str]
    urls: list[str]


@dataclass
class ResearchrDetail:
    abstract: str = ""
    url: str = ""
    urls: list[str] = field(default_factory=list)


class ResearchrScraper(Scraper):
    name = "researchr"

    def __init__(self, venue: VenueConfig, fetcher: Fetcher, **kwargs: Any) -> None:
        super().__init__(venue, fetcher, **kwargs)
        program_url = venue.source.get("program_url") or venue.source.get("url")
        if not program_url:
            raise ValueError(f"Venue {venue.id!r}: researchr requires source.program_url")
        self.program_url = str(program_url)
        self.context = str(venue.source.get("context") or self._infer_context(self.program_url))
        self.include_tracks = set(self._as_list(venue.source.get("include_tracks")))
        self.include_event_types = set(self._as_list(venue.source.get("include_event_types")))
        self.exclude_event_types = set(self._as_list(venue.source.get("exclude_event_types")))
        self.fetch_details = bool(venue.source.get("fetch_details", True))
        self.require_authors = bool(venue.source.get("require_authors", False))
        self.track_prefix = str(venue.source.get("track_prefix") or venue.series or "")

    def scrape(self) -> list[Paper]:
        html = self.fetcher.get_text(self.program_url, "program.html")
        occurrences, modal_config = self.parse_program(html)
        kept = [occ for occ in occurrences if self.keep_occurrence(occ)]
        events = self.merge_occurrences(kept)
        selected = events[: self.limit] if self.limit else events
        print(
            f"[{self.venue.id}] {len(selected)} Researchr events selected "
            f"from {len(occurrences)} program rows.",
            file=sys.stderr,
        )

        details = self.crawl_details(selected, modal_config) if self.fetch_details else {}
        return [self.to_paper(event, details.get(event.event_id)) for event in selected]

    def _abs(self, href: str) -> str:
        return urljoin(self.program_url, href) if href else ""

    @staticmethod
    def _as_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value]

    @staticmethod
    def _infer_context(program_url: str) -> str:
        parts = [part for part in urlparse(program_url).path.split("/") if part]
        if "program" in parts:
            idx = parts.index("program")
            if idx + 1 < len(parts):
                return parts[idx + 1]
        return ""

    def _normalize_track(self, value: str) -> str:
        track = re.sub(r"\s+", " ", value or "").strip()
        prefix = f"{self.track_prefix} " if self.track_prefix else ""
        if prefix and track.startswith(prefix):
            return track[len(prefix) :].strip()
        return track

    def parse_program(
        self, html: str
    ) -> tuple[list[ResearchrOccurrence], ResearchrModalConfig | None]:
        soup = BeautifulSoup(html, "html.parser")
        modal_config = self.parse_modal_config(soup)
        occurrences: list[ResearchrOccurrence] = []
        for table in soup.select("table.session-table"):
            session = self.parse_session(table)
            for row in table.select("tr[data-slot-id]"):
                occurrence = self.parse_occurrence(row, session)
                if occurrence:
                    occurrences.append(occurrence)
        return occurrences, modal_config

    def parse_modal_config(self, soup: BeautifulSoup) -> ResearchrModalConfig | None:
        loader = soup.select_one("#event-modal-loader")
        form = loader.select_one("form[action]") if loader else None
        if form is None:
            return None
        event_input = form.select_one("input.event-id-input[name]")
        action_anchor = form.select_one("#load-modal-action[submitid], a[submitid]")
        if event_input is None or action_anchor is None:
            return None
        context_input = form.select_one('input[name="context"]')
        context = context_input.get("value", "") if context_input else self.context
        return ResearchrModalConfig(
            action_url=self._abs(form.get("action", "")),
            action_name=action_anchor.get("submitid", ""),
            context=context or self.context,
            event_input_name=event_input.get("name", ""),
            form_name=form.get("name", "") or form.get("id", ""),
        )

    def parse_session(self, table: Tag) -> dict[str, str]:
        detail = table.select_one("tr.session-details")
        info = detail.select_one(".session-info-in-table") if detail else None
        slot_label = clean_text(detail.select_one(".slot-label")) if detail else ""
        location = clean_text(info.select_one(".room-link")) if info else ""
        if not location:
            location = table.get("data-facet-room", "")
        session_title = self.parse_session_title(info)
        date = table.get("data-facet-date", "")
        return {
            "date": date,
            "location": location,
            "slot_label": slot_label,
            "title": session_title,
            "id": safe_slug(f"{date}-{location}-{slot_label}-{session_title}"),
        }

    @staticmethod
    def parse_session_title(info: Tag | None) -> str:
        if info is None:
            return ""
        chunks: list[str] = []
        for child in info.children:
            if isinstance(child, NavigableString):
                text = str(child).strip()
                if text:
                    chunks.append(text)
                continue
            if not isinstance(child, Tag):
                continue
            classes = child.get("class") or []
            if child.name in {"br", "p"} or "pull-right" in classes or "room-link" in classes:
                break
            text = clean_text(child)
            if text:
                chunks.append(text)
        title = re.sub(r"\s+", " ", " ".join(chunks)).strip()
        if title:
            return title
        fallback = clean_text(info)
        return re.split(r"\s+at\s+|\s+Chair\(s\):", fallback, maxsplit=1)[0].strip()

    def parse_occurrence(
        self, row: Tag, session: dict[str, str]
    ) -> ResearchrOccurrence | None:
        title_anchor = row.select_one("a[data-event-modal]")
        if title_anchor is None:
            return None
        event_id = title_anchor.get("data-event-modal", "")
        if not event_id:
            return None

        tracks = unique_preserve_order(
            [
                self._normalize_track(clean_text(node))
                for node in row.select(".prog-track")
                if clean_text(node)
            ]
        )
        facet_tracks = unique_preserve_order(
            [
                self._normalize_track(str(node.get("data-facet-track", "")))
                for node in row.select("[data-facet-track]")
                if node.get("data-facet-track")
            ]
        )
        people = self.parse_people(row.select_one(".performers"))
        urls = [
            self._abs(anchor.get("href", ""))
            for anchor in row.select("a.publication-link[href]")
            if anchor.get("href") and anchor.get("href") != "#"
        ]

        date = self.format_event_date(
            session.get("date", ""),
            clean_text(row.select_one(".start-time")),
            clean_text(row.select_one(".text-muted strong")),
        )
        return ResearchrOccurrence(
            event_id=event_id,
            slot_id=row.get("data-slot-id", ""),
            title=self.parse_event_title(title_anchor),
            event_type=clean_text(row.select_one(".event-type")),
            tracks=tracks,
            facet_tracks=facet_tracks,
            authors=[person["name"] for person in people if person.get("name")],
            author_institutions="; ".join(
                f"{person['name']} ({person['institution']})"
                if person.get("institution")
                else person["name"]
                for person in people
                if person.get("name")
            ),
            session_id=session.get("id", ""),
            session_title=session.get("title", ""),
            date=date,
            location=session.get("location", ""),
            urls=unique_preserve_order(urls),
        )

    @staticmethod
    def parse_event_title(anchor: Tag) -> str:
        chunks: list[str] = []

        def collect(node: Tag | NavigableString) -> None:
            if isinstance(node, NavigableString):
                text = str(node).strip()
                if text:
                    chunks.append(text)
                return
            classes = node.get("class") or []
            if any(skip in classes for skip in ("pull-right", "output-badge", "label")):
                return
            for child in node.children:
                if isinstance(child, (Tag, NavigableString)):
                    collect(child)

        collect(anchor)
        return re.sub(r"\s+", " ", " ".join(chunks)).strip()

    @staticmethod
    def parse_people(container: Tag | None) -> list[dict[str, str]]:
        if container is None:
            return []
        people: list[dict[str, str]] = []
        for anchor in container.select('a[href*="/profile/"]'):
            name = clean_text(anchor)
            if not name:
                continue
            institution = ""
            sibling = anchor.next_sibling
            while sibling is not None:
                if isinstance(sibling, Tag) and sibling.name == "a":
                    break
                if isinstance(sibling, Tag) and "prog-aff" in (sibling.get("class") or []):
                    institution = clean_text(sibling)
                    break
                sibling = sibling.next_sibling
            people.append({"name": name, "institution": institution})
        return people

    @classmethod
    def format_event_date(cls, date: str, start: str, duration: str) -> str:
        if not date:
            return ""
        if not start:
            return date
        minutes = cls.parse_duration_minutes(duration)
        if minutes is None:
            return f"{date} {start}"
        try:
            start_dt = datetime.strptime(f"{date} {start}", "%a %d %b %Y %H:%M")
        except ValueError:
            return f"{date} {start}"
        end_dt = start_dt + timedelta(minutes=minutes)
        return f"{date} {start} - {end_dt.strftime('%H:%M')}"

    @staticmethod
    def parse_duration_minutes(duration: str) -> int | None:
        compact = re.sub(r"\s+", "", duration or "")
        match = DURATION_RE.match(compact)
        if not match:
            return None
        hours = int(match.group(1) or 0)
        minutes = int(match.group(2) or 0)
        total = hours * 60 + minutes
        return total if total else None

    def keep_occurrence(self, occurrence: ResearchrOccurrence) -> bool:
        if not occurrence.title:
            return False
        if self.require_authors and not occurrence.authors:
            return False
        if self.include_event_types and occurrence.event_type not in self.include_event_types:
            return False
        if self.exclude_event_types and occurrence.event_type in self.exclude_event_types:
            return False
        if self.include_tracks:
            track_names = set(occurrence.tracks + occurrence.facet_tracks)
            if not track_names.intersection(self.include_tracks):
                return False
        return True

    @staticmethod
    def merge_occurrences(occurrences: list[ResearchrOccurrence]) -> list[ResearchrEvent]:
        grouped: OrderedDict[str, ResearchrEvent] = OrderedDict()
        for occurrence in occurrences:
            event = grouped.get(occurrence.event_id)
            if event is None:
                grouped[occurrence.event_id] = ResearchrEvent(
                    event_id=occurrence.event_id,
                    title=occurrence.title,
                    event_types=[occurrence.event_type],
                    tracks=list(occurrence.tracks),
                    facet_tracks=list(occurrence.facet_tracks),
                    authors=list(occurrence.authors),
                    author_institutions=occurrence.author_institutions,
                    slot_ids=[occurrence.slot_id],
                    session_ids=[occurrence.session_id],
                    session_titles=[occurrence.session_title],
                    dates=[occurrence.date],
                    locations=[occurrence.location],
                    urls=list(occurrence.urls),
                )
                continue

            event.event_types = unique_preserve_order(event.event_types + [occurrence.event_type])
            event.tracks = unique_preserve_order(event.tracks + occurrence.tracks)
            event.facet_tracks = unique_preserve_order(event.facet_tracks + occurrence.facet_tracks)
            event.slot_ids = unique_preserve_order(event.slot_ids + [occurrence.slot_id])
            event.session_ids = unique_preserve_order(event.session_ids + [occurrence.session_id])
            event.session_titles = unique_preserve_order(event.session_titles + [occurrence.session_title])
            event.dates = unique_preserve_order(event.dates + [occurrence.date])
            event.locations = unique_preserve_order(event.locations + [occurrence.location])
            event.urls = unique_preserve_order(event.urls + occurrence.urls)
            if not event.authors and occurrence.authors:
                event.authors = list(occurrence.authors)
                event.author_institutions = occurrence.author_institutions

        return sorted(grouped.values(), key=lambda event: event.event_id)

    def crawl_details(
        self,
        events: list[ResearchrEvent],
        modal_config: ResearchrModalConfig | None,
    ) -> dict[str, ResearchrDetail]:
        if modal_config is None:
            print(f"[{self.venue.id}] no Researchr modal loader found; skipping details.", file=sys.stderr)
            return {}

        def fetch_one(event: ResearchrEvent) -> tuple[str, ResearchrDetail]:
            payload = [
                (modal_config.action_name, "1"),
                ("__ajax_runtime_request__", modal_config.placeholder_id),
                ("context", modal_config.context),
            ]
            if modal_config.form_name:
                payload.append((modal_config.form_name, "1"))
            payload.append((modal_config.event_input_name, event.event_id))
            response = self.fetcher.post_text(
                modal_config.action_url,
                f"modals/{safe_slug(event.event_id)}.json",
                payload,
            )
            return event.event_id, self.parse_modal_response(response)

        if self.workers <= 1:
            return dict(fetch_one(event) for event in events)

        details: dict[str, ResearchrDetail] = {}
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(fetch_one, event): event for event in events}
            completed = 0
            for future in as_completed(futures):
                event = futures[future]
                completed += 1
                try:
                    event_id, detail = future.result()
                    details[event_id] = detail
                except Exception as exc:  # noqa: BLE001 - keep the crawl resilient
                    print(f"[{self.venue.id}] detail fetch failed for {event.event_id}: {exc}", file=sys.stderr)
                if completed % 100 == 0:
                    print(f"[{self.venue.id}] fetched {completed}/{len(events)} detail modals...", file=sys.stderr)
        return details

    def parse_modal_response(self, text: str) -> ResearchrDetail:
        html = ""
        try:
            commands = json.loads(text)
        except json.JSONDecodeError:
            html = text
        else:
            html = "".join(
                str(command.get("value", ""))
                for command in commands
                if command.get("action") in {"append", "replace"}
            )

        soup = BeautifulSoup(html, "html.parser")
        detail_links = [
            self._abs(anchor.get("href", ""))
            for anchor in soup.select('a[href*="/details/"]')
            if anchor.get("href")
        ]
        detail_url = detail_links[0] if detail_links else ""

        description = soup.select_one(".event-description")
        abstract = ""
        extra_urls: list[str] = []
        if description is not None:
            paragraphs = [
                clean_text(paragraph)
                for paragraph in description.find_all("p", recursive=False)
                if clean_text(paragraph)
            ]
            abstract = " ".join(paragraphs)
            if not abstract:
                for row in description.select(".row"):
                    row.extract()
                abstract = clean_text(description)
            extra_urls = [
                self._abs(anchor.get("href", ""))
                for anchor in description.select("a[href]")
                if anchor.get("href")
                and "/profile/" not in anchor.get("href", "")
                and "/details/" not in anchor.get("href", "")
            ]

        return ResearchrDetail(
            abstract=abstract,
            url=detail_url,
            urls=unique_preserve_order(extra_urls),
        )

    def to_paper(self, event: ResearchrEvent, detail: ResearchrDetail | None = None) -> Paper:
        detail = detail or ResearchrDetail()
        urls = unique_preserve_order([detail.url] + event.urls + detail.urls + [self.program_url])
        return Paper(
            id=event.event_id,
            title=event.title,
            abstract=detail.abstract,
            authors=list(event.authors),
            author_institutions=event.author_institutions,
            tracks=list(event.tracks),
            event_type="; ".join(event.event_types),
            session_titles=list(event.session_titles),
            sessions=list(event.session_ids),
            dates=list(event.dates),
            locations=list(event.locations),
            urls=urls,
        )
