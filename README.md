# DAC 2026 Program Scraper

Crawl the Linklings program data from `https://63dac.conference-program.com/` and export DAC 2026 paper tables.

By default, the scraper only includes `RESEARCH*` presentations, which correspond to `Research Manuscript` entries on the site. It preserves two export views:

- `data/dac2026_papers.csv`: one row per paper, deduplicated by `presentation_id`.
- `data/dac2026_paper_presentations.csv`: one row per `presentation_id + session_id`, preserving cases where the same paper appears in multiple sessions.

The scraper also writes matching JSON files that preserve nested fields such as authors, institutions, recommended presentations, and page information sections.

## Run

```bash
uv run dac26
```

Fetch only a few detail pages while debugging:

```bash
uv run dac26 --limit 5
```

Fetch every presentation type instead of only research papers:

```bash
uv run dac26 --all-presentations
```

Refresh the cache and fetch pages again:

```bash
uv run dac26 --refresh
```

## Output Fields

The paper table includes title, authors, author institutions, abstract, event type, track/category, session, date, location, URL, page information sections as JSON, complete occurrence records as JSON, and related fields.

The scraper writes the 7 date snippets discovered from the home page, link counts, prefix statistics, and fetch status counts to `data/dac2026_metadata.json` so completeness can be checked.

## Static Website

The static website lives in `docs/` and is ready for GitHub Pages. It includes:

- `docs/index.html`: searchable paper list with local favorite buttons.
- `docs/favorites.html`: favorite-only view.
- `docs/data/papers.json`: compact paper data used by the website.

Favorites are stored in browser `localStorage`, so the site does not need a backend.

To preview locally:

```bash
python3 -m http.server 8000 --directory docs
```

Then open `http://localhost:8000/`.

To deploy on GitHub Pages, set the Pages source to the repository branch and `/docs` folder.
