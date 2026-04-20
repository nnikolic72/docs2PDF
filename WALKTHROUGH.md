# docs2PDF Project Walkthrough

## 1. Project Overview
**docs2PDF** is a terminal-based application (TUI) designed to download online documentation and convert it into a single, high-quality PDF optimized for the **reMarkable Paper Pro**.

### Key Features
- **Project Management**: Create, edit, and archive documentation projects.
- **Intelligent Crawling**: Automatically follows documentation hierarchies, staying within the root domain and specified depth.
- **Clean Extraction**: Strips ads, headers, and footers to keep only content and images.
- **reMarkable Optimization**: Generates PDFs with specific dimensions (2160x1620) and breadcrumb navigation.
- **Background Operations**: All downloading and processing happens in the background without freezing the UI.

## 2. Technical Stack
- **Python 3.13**: Using `uv` for lightning-fast dependency management.
- **Textual**: Modern TUI framework for a responsive and dynamic terminal interface.
- **SQLite3**: Robust local storage for project metadata.
- **Scraping Engine**: `httpx` (async) + `BeautifulSoup4` (parsing) + `Trafilatura` (content extraction).
- **PDF Engine**: `WeasyPrint` + `Jinja2` for high-fidelity PDF generation with modern CSS.
- **Quality Assurance**: `pytest` (TDD), `ruff` (linting/formatting), `ty` (static type checking), and `pre-commit` hooks.

## 3. Architecture & Principles
- **TDD (Test Driven Development)**: Every feature begins with a failing test.
- **SOLID & DRY**: Modular design ensuring single responsibility and reusability.
- **Layered Design**:
    - **UI Layer**: Textual screens and widgets.
    - **Service Layer**: Crawler and PDF generator logic.
    - **Data Layer**: SQLite repository for persistence.
    - **Storage Layer**: Local filesystem (`projects/` directory) for raw assets and final PDFs.

## 4. Implementation Roadmap
- **Phase 1**: Initialize `uv` project, configure `ruff`, `ty`, `pytest`, and `pre-commit`.
- **Phase 2**: Implement SQLite data model and CRUD operations (TDD).
- **Phase 3**: Build the async crawler and content extraction engine.
- **Phase 4**: Develop the PDF generation pipeline with Jinja2 templates and CSS.
- **Phase 5**: Construct the Textual TUI and integrate background workers.

## 5. Next Step
Upon your approval, I will begin **Phase 1**: Initializing the Python 3.13 project with `uv` and setting up the development environment (linting, types, and testing).
