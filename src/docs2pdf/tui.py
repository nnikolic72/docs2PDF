import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static, TextArea, Tree

from docs2pdf.crawler import Crawler
from docs2pdf.database import DatabaseManager, Page, Project
from docs2pdf.generator import PDFGenerator
from docs2pdf.widgets import CheckboxTree, DownloadProgress


class ProjectListScreen(Screen):
    """The main screen listing all documentation projects."""

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DataTable(id="projects_table"),
            classes="main-container",
        )
        yield Horizontal(
            Button("Add Project", variant="success", id="add_btn"),
            Button("Open/Resume", id="open_btn"),
            Button("Edit", id="edit_btn"),
            Button("Reset Project", variant="warning", id="reset_btn"),
            Button("Archive", variant="error", id="archive_btn"),
            id="controls",
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
            # Handle space-separated URLs
            urls = p.root_url.split(" ")
            display_url = urls[0]
            if len(urls) > 1:
                display_url += f" (+{len(urls) - 1} more)"
            table.add_row(str(p.id), p.name, display_url, p.status, key=str(p.id))

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

    @on(Button.Pressed, "#edit_btn")
    def action_edit_project(self) -> None:
        table = self.query_one(DataTable)
        if table.cursor_row is not None:
            project_id_str = table.get_row_at(table.cursor_row)[0]
            project_id = int(project_id_str)
            db = self.app.db  # type: ignore
            project = db.get_project(project_id)
            if project:

                def handle_edit(updated_project: Project | None) -> None:
                    if updated_project:
                        self._refresh_projects()

                self.app.push_screen(EditProjectScreen(project), callback=handle_edit)

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
                safe_name = project.name.replace(" ", "_").lower()

                # 1. Archive existing PDF if it exists
                pdf_path = project_dir / f"{safe_name}.pdf"
                if pdf_path.exists():
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archive_path = project_dir / f"{safe_name}_archive_{timestamp}.pdf"
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


class EditProjectScreen(Screen[Project]):
    """Screen for editing an existing documentation project."""

    def __init__(self, project: Project):
        super().__init__()
        self.project = project

    def compose(self) -> ComposeResult:
        yield Container(
            Container(
                Static(f"Edit Project: {self.project.name}", id="title"),
                Static("Project Name:", classes="label"),
                Input(value=self.project.name, placeholder="Project Name", id="project_name"),
                Static("Exclude patterns (comma-separated):", classes="label"),
                Input(value=self.project.exclude_patterns, placeholder="Exclude patterns", id="exclude_patterns"),
                id="form",
            ),
            classes="main-container centered-content",
        )
        yield Horizontal(
            Button("Save", variant="success", id="save_btn"),
            Button("Cancel", id="cancel_btn"),
            classes="button-bar",
        )

    @on(Button.Pressed, "#save_btn")
    def save_changes(self) -> None:
        new_name = self.query_one("#project_name", Input).value
        new_exclude = self.query_one("#exclude_patterns", Input).value

        updates: dict[str, Any] = {}
        if new_name and new_name != self.project.name:
            # 1. Rename directory if it exists
            old_dir = Path("projects") / self.project.name
            new_dir = Path("projects") / new_name

            if old_dir.exists():
                try:
                    old_dir.rename(new_dir)
                except Exception as e:
                    # In a real app we might want to show an error message
                    print(f"Error renaming directory: {e}")
            updates["name"] = new_name

        if new_exclude != self.project.exclude_patterns:
            updates["exclude_patterns"] = new_exclude

        if updates:
            db = self.app.db  # type: ignore
            db.update_project(self.project.id, updates)
            # Return updated project
            self.project.name = new_name
            self.project.exclude_patterns = new_exclude
            self.dismiss(self.project)
        else:
            self.dismiss(None)

    @on(Button.Pressed, "#cancel_btn")
    def cancel(self) -> None:
        self.dismiss(None)


class AddProjectScreen(Screen):
    """Screen for adding a new documentation project."""

    def compose(self) -> ComposeResult:
        yield Container(
            Container(
                Static("New Project Details", id="title"),
                Input(placeholder="Project Name", id="project_name"),
                Static("Root URLs (pasted text will be parsed):", classes="label"),
                TextArea(id="root_urls"),
                Input(placeholder="Exclude patterns (comma-separated, e.g., /api/,/v1/)", id="exclude_patterns"),
                id="form",
            ),
            classes="main-container centered-content",
        )
        yield Horizontal(
            Button("Save", variant="success", id="save_btn"),
            Button("Cancel", id="cancel_btn"),
            classes="button-bar",
        )

    @on(Button.Pressed, "#save_btn")
    def save_project(self) -> None:
        name = self.query_one("#project_name", Input).value
        text = self.query_one("#root_urls", TextArea).text
        exclude_patterns = self.query_one("#exclude_patterns", Input).value

        # Extract all URLs from pasted text
        found_urls = re.findall(r"https?://[^\s]+", text)

        # Deduplicate while preserving order
        seen = set()
        ordered_urls = []
        for u in found_urls:
            # Basic cleanup: remove trailing punctuation that might be part of the text but not the URL
            u = u.rstrip(".,;!?)")
            if u not in seen:
                ordered_urls.append(u)
                seen.add(u)

        if name and ordered_urls:
            # Store as a space-separated string in the DB
            urls_str = " ".join(ordered_urls)
            db = self.app.db  # type: ignore
            project_id = db.add_project(Project(name=name, root_url=urls_str, exclude_patterns=exclude_patterns))
            self.app.pop_screen()
            self.app.call_after_refresh(self._start_discovery, project_id, urls_str, name)

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
            Static("Initializing...", id="current_url"),
            DownloadProgress(id="discovery_progress"),
            Static("This might take a minute depending on the site size.", id="status"),
            id="discovery_container",
        )

    def on_mount(self) -> None:
        self.run_discovery()

    @work(exclusive=True)
    async def run_discovery(self) -> None:
        progress = self.query_one("#discovery_progress", DownloadProgress)
        current_url_label = self.query_one("#current_url", Static)

        def on_progress(url: str, status: str):
            progress.update_status(url, status)
            if status == "downloading":
                current_url_label.update(f"Fetching: [bold]{url}[/bold]")

        db = self.app.db  # type: ignore
        project = db.get_project(self.project_id)
        exclude_patterns = (
            [p.strip() for p in project.exclude_patterns.split(",")] if project and project.exclude_patterns else []
        )

        crawler = Crawler(self.root_url, self.project_name, exclude_patterns=exclude_patterns)
        pages_info = await crawler.discover_hierarchy(max_depth=6, on_progress=on_progress)

        # Save to DB
        db = self.app.db  # type: ignore
        url_to_db_id = {}
        # First pass: add all pages
        for info in pages_info:
            page = Page(project_id=self.project_id, url=info["url"], title=info["title"])
            db_id = db.add_page(page)
            url_to_db_id[info["url"]] = db_id

        # Second pass: update parent IDs
        for info in pages_info:
            if info["parent_url"] and info["parent_url"] in url_to_db_id:
                # Update the page in DB with parent_id
                page_id = url_to_db_id[info["url"]]
                parent_id = url_to_db_id[info["parent_url"]]
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
            classes="main-container",
        )
        yield Horizontal(
            Button("Download Selected", variant="success", id="download_btn"),
            Button("Back", id="back_btn"),
            classes="button-bar",
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

    @on(Button.Pressed, "#back_btn")
    def action_back(self) -> None:
        self.app.pop_screen()


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
            Static("Initializing...", id="current_url"),
            DownloadProgress(id="download_progress"),
            Static("Preparing...", id="progress_log"),
            id="crawler_container",
        )
        yield Horizontal(
            Button("Stop", variant="error", id="stop_btn"),
            classes="button-bar",
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
        progress = self.query_one("#download_progress", DownloadProgress)
        current_url_label = self.query_one("#current_url", Static)
        log.update("Starting crawler...")

        def on_progress(url: str, status: str):
            progress.update_status(url, status)
            if status == "downloading":
                current_url_label.update(f"Fetching: [bold]{url}[/bold]")

        exclude_patterns = [p.strip() for p in project.exclude_patterns.split(",")] if project.exclude_patterns else []
        crawler = Crawler(project.root_url, project.name, exclude_patterns=exclude_patterns)
        await crawler.run(selected_urls=selected_urls, on_progress=on_progress)

        current_url_label.update("Done.")
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
        padding: 1 2;
    }
    TextArea {
        height: 10;
        margin-top: 1;
        margin-bottom: 1;
    }
    .label {
        margin-top: 1;
        color: $text-muted;
    }
    #controls, .button-bar {
        height: auto;
        min-height: 3;
        margin-top: 1;
        align: center middle;
        width: 100%;
    }
    .main-container {
        height: 1fr;
    }
    .centered-content {
        align: center middle;
    }
    DataTable, CheckboxTree {
        height: 1fr;
    }
    #discovery_container, #crawler_container {
        height: 1fr;
    }

    /* Pastel Button Styling */
    Button {
        margin-right: 1;
        border: none;
        text-style: bold;
    }
    Button:hover {
        text-style: bold underline;
    }

    /* Pastel Green: Add, Save, Download */
    #add_btn, #save_btn, #download_btn {
        background: #B4E197;
        color: #2C3333;
    }

    /* Pastel Blue: Open, Edit, Back */
    #open_btn, #edit_btn, #back_btn {
        background: #A0C4FF;
        color: #2C3333;
    }

    /* Pastel Red/Pink: Archive, Stop, Cancel */
    #archive_btn, #stop_btn, #cancel_btn {
        background: #FFADAD;
        color: #2C3333;
    }

    /* Pastel Yellow: Reset */
    #reset_btn {
        background: #FDFFB6;
        color: #2C3333;
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
