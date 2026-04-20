# docs2PDF Project Guidelines

This file provides foundational mandates for the docs2PDF project. These rules must be strictly followed by all Gemini agents.

## Tech Stack & Architecture
- **Language**: Python 3.13
- **Dependency Management**: `uv`
- **Testing**: `pytest` (with maximal coverage), `conftest.py` for shared fixtures
- **Linting & Formatting**: `ruff` (exclude conflicting formatter rules, 120 characters line length limit)
- **Type Checking**: `ty`
- **Pre-commit**: `pre-commit` (ruff, ty, common python hooks)
- **TUI Framework**: `textual` (for responsive, terminal-sized UI with background workers)
- **Web Scraping**: `httpx` (async), `beautifulsoup4`, `trafilatura` (for clean content extraction without ads/headers/footers).
    - **Session Management**: Re-use `httpx.AsyncClient` across requests to minimize overhead.
    - **Caching**: Implement and use an in-memory page cache for a single session to prevent redundant fetches during discovery/crawling.
    - **Politeness**: Always include small delays (`asyncio.sleep`) between requests and be mindful of 429 errors.
- **PDF Generation**: `weasyprint` (customized CSS for reMarkable Paper Pro: 11.8" screen, 2160x1620 resolution)
    - **macOS Compatibility**: Ensure search paths for system libraries (Pango/Cairo) include Homebrew locations.
- **Database**: SQLite3 (latest built-in version) using Python `dataclasses`.
    - **Type Safety**: Use `TypedDict` for partial updates to ensure data integrity.
- **Data Storage**: Downloaded content (HTML, images) and PDFs must be stored locally under a `projects/` directory, segregated by project name.

## Engineering Principles
- **SOLID & DRY**: Code must be modular, single-responsibility, and highly reusable.
- **Test-Driven Development (TDD)**: ALWAYS write tests before writing or changing code. Use the red/green workflow and small, focused commits.
- **Step-by-Step Implementation**: Implement the system incrementally according to the approved plan. Do not rush or bundle large features together.

## Specific Requirements
- Background downloading: Use Textual's async workers to handle crawling and parsing without blocking the UI.
- Scraped content must accurately maintain the documentation's hierarchy.
- HTML links pointing to other pages in the documentation must be converted into internal PDF navigation links.
- Only crawl links on the same domain and at the same or deeper hierarchical level as the provided root URL.
- Inject PDF breadcrumbs at the top of extracted pages for easy hierarchy navigation.
- PDF generation must produce a single, beautifully formatted file optimized for the reMarkable Paper Pro.

## Development Commands
You can use `make` or `uv run` to perform common development tasks.
- **Run tests:** `make test` or `uv run pytest`
- **Lint code (and sort imports):** `make lint` or `uv run ruff check .`
  - To automatically fix lint errors and sort imports: `uv run ruff check --fix .`
  - To run type checker: `uv run ty check src/`
- **Format code:** `make format` or `uv run ruff format .`
- **Run the app:** `make run` or `PYTHONPATH=src uv run python -m docs2pdf`
