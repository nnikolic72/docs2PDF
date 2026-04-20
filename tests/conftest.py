from pathlib import Path

import pytest


@pytest.fixture
def tmp_projects_dir(tmp_path: Path) -> Path:
    """Fixture to provide a temporary projects directory."""
    projects_dir = tmp_path / "projects"
    projects_dir.mkdir()
    return projects_dir


@pytest.fixture
def sample_html_content() -> str:
    """Fixture to provide sample HTML content."""
    return """
    <html>
        <head><title>Test Page</title></head>
        <body>
            <header>Header Content</header>
            <main>
                <h1>Main Title</h1>
                <p>Content text here.</p>
                <img src="image.png">
                <a href="/subpage">Sublink</a>
                <a href="https://external.com">External</a>
            </main>
            <footer>Footer Content</footer>
            <div class="ads">Ad content</div>
        </body>
    </html>
    """
