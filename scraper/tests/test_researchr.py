import json
from pathlib import Path

from confer.config import VenueConfig
from confer.fetcher import Fetcher
from confer.scrapers.researchr import ResearchrScraper

FIXTURES = Path(__file__).parent / "fixtures"


def make_scraper(tmp_path: Path) -> ResearchrScraper:
    venue = VenueConfig(
        id="test",
        name="Test",
        series="ICSE",
        scraper="researchr",
        source={
            "program_url": "https://conf.researchr.org/program/icse-2026/program-icse-2026/",
            "context": "icse-2026",
            "include_tracks": ["Research Track"],
            "include_event_types": ["Talk"],
            "require_authors": True,
        },
    )
    return ResearchrScraper(venue, Fetcher(tmp_path, refresh=False))


def test_parse_program_extracts_occurrence_and_modal_config(tmp_path):
    scraper = make_scraper(tmp_path)
    html = (FIXTURES / "researchr_program.html").read_text(encoding="utf-8")
    occurrences, modal_config = scraper.parse_program(html)

    assert modal_config is not None
    assert modal_config.action_name == "modal_action"
    assert modal_config.event_input_name == "event_field"
    assert modal_config.form_name == "form_modal"
    assert modal_config.context == "icse-2026"

    assert len(occurrences) == 1
    occurrence = occurrences[0]
    assert occurrence.event_id == "event-1"
    assert occurrence.slot_id == "slot-1"
    assert occurrence.title == (
        "MazeBreaker: Multi-Agent Reinforcement Learning for Dynamic Jailbreaking "
        "of LLM Security Defenses"
    )
    assert occurrence.event_type == "Talk"
    assert occurrence.tracks == ["Research Track"]
    assert occurrence.facet_tracks == ["Research Track", "SE In Practice (SEIP)"]
    assert occurrence.authors == ["Zhihao Lin", "Wei Ma"]
    assert occurrence.author_institutions == "Zhihao Lin; Wei Ma (Singapore Management University)"
    assert occurrence.session_title == "Software Engineering for AI 2"
    assert occurrence.date == "Wed 15 Apr 2026 14:00 - 14:15"
    assert occurrence.location == "Oceania VII"
    assert occurrence.urls == ["https://arxiv.org/pdf/2503.17953"]
    assert scraper.keep_occurrence(occurrence)


def test_modal_response_and_paper_schema(tmp_path):
    scraper = make_scraper(tmp_path)
    html = (FIXTURES / "researchr_program.html").read_text(encoding="utf-8")
    occurrences, _ = scraper.parse_program(html)
    event = scraper.merge_occurrences([occurrences[0]])[0]
    modal_html = """
    <div class="modal">
      <div class="modal-body">
        <div class="bg-primary event-title"><h4>MazeBreaker</h4></div>
        <div class="bg-info event-description">
          <p>Adaptive jailbreak attack abstract.</p>
          <div class="row"><a href="/profile/icse-2026/zhihaolin1">Zhihao Lin</a></div>
          <a href="https://example.org/artifact">Artifact</a>
        </div>
      </div>
      <div class="modal-footer">
        <a href="https://conf.researchr.org/details/icse-2026/icse-2026-research-track/41/MazeBreaker">All Details</a>
      </div>
    </div>
    """
    detail = scraper.parse_modal_response(
        json.dumps([{"action": "append", "id": "event-modals", "value": modal_html}])
    )
    paper = scraper.to_paper(event, detail)

    assert detail.abstract == "Adaptive jailbreak attack abstract."
    assert paper.id == "event-1"
    assert paper.abstract == "Adaptive jailbreak attack abstract."
    assert paper.urls[0].endswith("/MazeBreaker")
    assert paper.urls[1] == "https://arxiv.org/pdf/2503.17953"
    assert paper.urls[2] == "https://example.org/artifact"
    assert paper.tracks == ["Research Track"]
    assert paper.event_type == "Talk"
    assert paper.sessions == ["Wed_15_Apr_2026-Oceania_VII-14_00_-_15_30-Software_Engineering_for_AI_2"]

    assert set(paper.to_dict()) == {
        "id",
        "title",
        "abstract",
        "authors",
        "authorInstitutions",
        "tracks",
        "eventType",
        "sessionTitles",
        "sessions",
        "dates",
        "locations",
        "urls",
    }
