from pathlib import Path

from confcrawl.config import VenueConfig
from confcrawl.fetcher import Fetcher
from confcrawl.scrapers.linklings import (
    LinkOccurrence,
    LinklingsScraper,
    natural_key,
    prefix_for,
)

FIXTURES = Path(__file__).parent / "fixtures"


def make_scraper(tmp_path: Path) -> LinklingsScraper:
    venue = VenueConfig(
        id="test",
        name="Test",
        scraper="linklings",
        source={"base_url": "https://example.conference-program.com/"},
    )
    return LinklingsScraper(venue, Fetcher(tmp_path, refresh=False))


def test_prefix_for():
    assert prefix_for("RESEARCH123") == "RESEARCH"
    assert prefix_for("ENGPRES7") == "ENGPRES"


def test_natural_key_orders_numerically():
    ids = ["RESEARCH10", "RESEARCH2", "RESEARCH1"]
    assert sorted(ids, key=natural_key) == ["RESEARCH1", "RESEARCH2", "RESEARCH10"]


def test_parse_detail_extracts_core_fields(tmp_path):
    scraper = make_scraper(tmp_path)
    html = (FIXTURES / "RESEARCH004__sess155.html").read_text(encoding="utf-8")
    occ = LinkOccurrence(presentation_id="RESEARCH004", session_id="sess155", url="https://x/")
    row = scraper.parse_detail(html, occ, option_maps={})

    assert row["fetch_status"] == "ok"
    assert row["presentation_id"] == "RESEARCH004"
    assert row["title"]
    assert isinstance(row["authors"], list) and row["authors"]
    assert row["abstract"]


def test_aggregate_merges_sessions(tmp_path):
    scraper = make_scraper(tmp_path)
    rows = [
        {
            "presentation_id": "RESEARCH1", "session_id": "sessA", "fetch_status": "ok",
            "title": "T", "abstract": "A", "authors": ["Jane"], "author_institutions": "Jane (X)",
            "event_type": "Research Manuscript", "tracks": ["EDA"],
            "session_title": "S-A", "date": "Mon", "location": "R1", "url": "u1",
        },
        {
            "presentation_id": "RESEARCH1", "session_id": "sessB", "fetch_status": "ok",
            "title": "T", "abstract": "A", "authors": ["Jane"], "author_institutions": "Jane (X)",
            "event_type": "Research Manuscript", "tracks": ["Security"],
            "session_title": "S-B", "date": "Tue", "location": "R2", "url": "u2",
        },
    ]
    papers = scraper.aggregate_to_papers(rows)
    assert len(papers) == 1
    paper = papers[0]
    assert paper.sessions == ["sessA", "sessB"]
    assert paper.tracks == ["EDA", "Security"]
    assert paper.dates == ["Mon", "Tue"]
    assert paper.authors == ["Jane"]
    d = paper.to_dict()
    assert set(d) == {
        "id", "title", "abstract", "authors", "authorInstitutions", "tracks",
        "eventType", "sessionTitles", "sessions", "dates", "locations", "urls",
    }
