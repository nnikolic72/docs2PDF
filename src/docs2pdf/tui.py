import shutil
from datetime import datetime
from pathlib import Path

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static, Tree

from docs2pdf.crawler import Crawler
from docs2pdf.database import DatabaseManager, Page, Project
from docs2pdf.generator import PDFGenerator
from docs2pdf.widgets import CheckboxTree


class ProjectListScreen(Screen):
    """The main screen listing all documentation projects."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTable(id="projects_table"),
            Horizontal(
                Button("Add Project", variant="success", id="add_btn"),
                Button("Open/Resume", id="open_btn"),
                Button("Reset Project", variant="warning", id="reset_btn"),
                Button("Archive", variant="error", id="archive_btn"),
                id="controls",
            ),
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("ID", "Name", "Root URL", "Status")
        table.cursor_type = "row"
        self._refresh_projects()

    def _refresh_projects(self) -> None:
        db = self.app.db  # type: ignore
        table = self.query_one(DataTable)
        table.clear()
        projects = db.get_all_projects(include_archived=False)
        for p in projects:
            table.add_row(str(p.id), p.name, p.root_url, p.status, key=str(p.id))

    @on(Button.Pressed, "#add_btn")
    def action_add_project(self) -> None:
        self.app.push_screen(AddProjectScreen())

    @on(Button.Pressed, "#open_btn")
    @on(DataTable.RowSelected, "#projects_table")
    def action_open_project(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row is not None:
            project_id_str = table.get_row_at(table.cursor_row)[0]
            project_id = int(project_id_str)
            db = self.app.db  # type: ignore
            project = db.get_project(project_id)
            if project:
                pages = db.get_project_pages(project_id)
                if not pages:
                    self.app.push_screen(DiscoveryScreen(project_id, project.root_url, project.name))
                else:
                    self.app.push_screen(PageSelectionScreen(project_id, project.name))

    @on(Button.Pressed, "#reset_btn")
    def action_reset_project(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row is not None:
            project_id_str = table.get_row_at(table.cursor_row)[0]
            project_id = int(project_id_str)
            db = self.app.db  # type: ignore
            project = db.get_project(project_id)
            if project:
                project_dir = Path("projects") / project.name

                # 1. Archive existing PDF if it exists
                pdf_path = project_dir / "documentation.pdf"
                if pdf_path.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archive_path = project_dir / f"documentation_archive_{timestamp}.pdf"
                    shutil.move(pdf_path, archive_path)

                # 2. Delete all downloaded files (content and images directories)
                content_dir = project_dir / "content"
                if content_dir.exists():
                    shutil.rmtree(content_dir)
                images_dir = project_dir / "images"
                if images_dir.exists():
                    shutil.rmtree(images_dir)

                # 3. Clear database pages and update status
                db.delete_project_pages(project_id)
                db.update_project(project_id, {"status": "pending"})

                # 4. Refresh UI and push discovery screen
                self._refresh_projects()
                self.app.push_screen(DiscoveryScreen(project_id, project.root_url, project.name))


class AddProjectScreen(Screen):
    """Screen for adding a new documentation project."""

    def compose(self) -> ComposeResult:
        yield Container(
            Static("New Project Details", id="title"),
            Input(placeholder="Project Name", id="project_name"),
            Input(placeholder="Root URL (e.g., https://example.com/docs/)", id="root_url"),
            Horizontal(
                Button("Save", variant="success", id="save_btn"),
                Button("Cancel", id="cancel_btn"),
            ),
            id="form",
        )

    @on(Button.Pressed, "#save_btn")
    def save_project(self) -> None:
        name = self.query_one("#project_name", Input).value
        url = self.query_one("#root_url", Input).value

        if name and url:
            db = self.app.db  # type: ignore
            project_id = db.add_project(Project(name=name, root_url=url))
            self.app.pop_screen()
            self.app.call_after_refresh(self._start_discovery, project_id, url, name)

    def _start_discovery(self, project_id: int, url: str, name: str) -> None:
        self.app.push_screen(DiscoveryScreen(project_id, url, name))

    @on(Button.Pressed, "#cancel_btn")
    def cancel(self) -> None:
        self.app.pop_screen()


class DiscoveryScreen(Screen):
    """Screen for the initial discovery scan of the documentation tree."""

    def __init__(self, project_id: int, root_url: str, project_name: str):
        super().__init__()
        self.project_id = project_id
        self.root_url = root_url
        self.project_name = project_name

    def compose(self) -> ComposeResult:
        yield Container(
            Static(f"Discovering hierarchy for {self.project_name}..."),
            Static("This might take a minute depending on the site size.", id="status"),
            id="discovery_container",
        )

    def on_mount(self) -> None:
        self.run_discovery()

    @work(exclusive=True)
    async def run_discovery(self) -> None:
        crawler = Crawler(self.root_url, self.project_name)
        pages_info = await crawler.discover_hierarchy(max_depth=3)

        # Save to DB
        db = self.app.db  # type: ignore
        url_to_db_id = {}
        # First pass: add all pages
        for info in pages_info:
            page = Page(project_id=self.project_id, url=info["url"], title=info["title"])
            db_id = db.add_page(page)
            url_to_db_id[info["url"]] = db_id

        # Second pass: update parent IDs
        # We need to add an update_page_parent method to db if we want to do it in two passes
        # or just be more clever in first pass.
        # Let's add a generic update_page method to database.py in next turn or fix it here.
        # For now, let's assume we can update it.
        for info in pages_info:
            if info["parent_url"] and info["parent_url"] in url_to_db_id:
                # Update the page in DB with parent_id
                page_id = url_to_db_id[info["url"]]
                parent_id = url_to_db_id[info["parent_url"]]
                # We'll need to implement this method in database.py
                db.update_page(page_id, {"parent_id": parent_id})

        self.app.pop_screen()
        self.app.push_screen(PageSelectionScreen(self.project_id, self.project_name))


class PageSelectionScreen(Screen):
    """Screen for selecting/deselecting documentation pages hierarchically."""

    def __init__(self, project_id: int, project_name: str):
        super().__init__()
        self.project_id = project_id
        self.project_name = project_name

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(f"Select pages for {self.project_name}", id="title"),
            CheckboxTree("Documentation", id="page_tree"),
            Horizontal(
                Button("Download Selected", variant="success", id="download_btn"),
                Button("Back", id="back_btn"),
            ),
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_tree()

    def _load_tree(self) -> None:
        db = self.app.db  # type: ignore
        pages = db.get_project_pages(self.project_id)
        tree = self.query_one(CheckboxTree)
        tree.root.expand()

        # Build hierarchy using a multi-pass approach for robustness
        nodes = {None: tree.root}
        pages_by_parent: dict[int | None, list[Page]] = {}
        for page in pages:
            pages_by_parent.setdefault(page.parent_id, []).append(page)

        def add_children(parent_id: int | None):
            for page in pages_by_parent.get(parent_id, []):
                parent_node = nodes[parent_id]
                new_node = parent_node.add(
                    page.title, data={"id": page.id, "is_selected": page.is_selected}, expand=True
                )
                nodes[page.id] = new_node
                add_children(page.id)

        add_children(None)

    @on(Tree.NodeSelected)
    def toggle_selection(self, event: Tree.NodeSelected) -> None:
        tree = self.query_one(CheckboxTree)
        tree.toggle_node(event.node)

        # Save change to DB
        db = self.app.db  # type: ignore
        if event.node.data:
            db.update_page_selection(event.node.data["id"], event.node.data["is_selected"], recursive=True)

    @on(Button.Pressed, "#download_btn")
    def start_download(self) -> None:
        self.app.push_screen(CrawlerProgressScreen(self.project_id, self.project_name))


class CrawlerProgressScreen(Screen):
    """Screen showing the background crawl progress and PDF generation."""

    def __init__(self, project_id: int, project_name: str):
        super().__init__()
        self.project_id = project_id
        self.project_name = project_name

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            Static(f"Downloading {self.project_name} in background..."),
            Static("Initializing...", id="progress_log"),
            Button("Stop", variant="error", id="stop_btn"),
        )
        yield Footer()

    def on_mount(self) -> None:
        self.run_crawler()

    @work(exclusive=True)
    async def run_crawler(self) -> None:
        db = self.app.db  # type: ignore
        project = db.get_project(self.project_id)
        pages = db.get_project_pages(self.project_id)
        selected_urls = {p.url for p in pages if p.is_selected}

        log = self.query_one("#progress_log", Static)
        log.update("Starting crawler...")

        crawler = Crawler(project.root_url, project.name)
        await crawler.run(selected_urls=selected_urls)

        log.update("Crawling complete. Generating PDF...")
        generator = PDFGenerator(project.name, project.root_url)
        pdf_path = generator.generate([p for p in pages if p.is_selected])

        log.update(f"Success! PDF generated at: {pdf_path}")
        self.query_one("#stop_btn", Button).label = "Close"

    @on(Button.Pressed, "#stop_btn")
    def stop_or_close(self) -> None:
        # Cancel workers if any
        for worker in self.workers:
            worker.cancel()
        self.app.pop_screen()


class Docs2PDFApp(App):
    """The main application class."""

    CSS = """
    Container {
        padding: 1;
    }
    #form {
        width: 60;
        height: auto;
        border: thick $primary;
        align: center middle;
    }
    #controls {
        height: 3;
        margin-top: 1;
    }
    """

    def __init__(self, db_path: Path):
        super().__init__()
        self.db = DatabaseManager(db_path)
        self.db.initialize()

    def on_mount(self) -> None:
        self.push_screen(ProjectListScreen())


if __name__ == "__main__":
    app = Docs2PDFApp(Path("docs2pdf.db"))
    app.run()
