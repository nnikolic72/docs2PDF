import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import NotRequired, TypedDict, cast


class ProjectUpdate(TypedDict):
    """Fields that can be updated for a project."""

    name: NotRequired[str]
    root_url: NotRequired[str]
    status: NotRequired[str]
    is_archived: NotRequired[bool]


class PageUpdate(TypedDict):
    """Fields that can be updated for a page."""

    project_id: NotRequired[int]
    url: NotRequired[str]
    title: NotRequired[str]
    parent_id: NotRequired[int | None]
    is_selected: NotRequired[bool]


@dataclass
class Project:
    """Project data model."""

    name: str
    root_url: str
    id: int | None = None
    status: str = "pending"
    is_archived: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class Page:
    """Page data model for documentation hierarchy selection."""

    project_id: int
    url: str
    title: str
    id: int | None = None
    parent_id: int | None = None
    is_selected: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class DatabaseManager:
    """Manager for the SQLite database."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _get_connection(self) -> sqlite3.Connection:
        """Helper to get an SQLite connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def initialize(self) -> None:
        """Create the tables if they don't exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    root_url TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    is_archived BOOLEAN NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    parent_id INTEGER,
                    is_selected BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects (id),
                    FOREIGN KEY (parent_id) REFERENCES pages (id)
                )
            """)

    def add_project(self, project: Project) -> int:
        """Add a new project to the database."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO projects (name, root_url, status, is_archived, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    project.name,
                    project.root_url,
                    project.status,
                    1 if project.is_archived else 0,
                    project.created_at.isoformat(),
                    project.updated_at.isoformat(),
                ),
            )
            return cast(int, cursor.lastrowid)

    def get_project(self, project_id: int) -> Project | None:
        """Retrieve a project by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if row:
                return self._row_to_project(row)
        return None

    def get_all_projects(self, include_archived: bool = False) -> list[Project]:
        """Retrieve all projects."""
        query = "SELECT * FROM projects"
        if not include_archived:
            query += " WHERE is_archived = 0"

        with self._get_connection() as conn:
            rows = conn.execute(query).fetchall()
            return [self._row_to_project(row) for row in rows]

    def update_project(self, project_id: int, updates: ProjectUpdate) -> None:
        """Update project details."""
        if not updates:
            return

        updated_at = datetime.now(UTC).isoformat()
        fields = []
        values = []
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            values.append(1 if key == "is_archived" and isinstance(value, bool) else value)

        values.extend([updated_at, project_id])
        query = f"UPDATE projects SET {', '.join(fields)}, updated_at = ? WHERE id = ?"
        with self._get_connection() as conn:
            conn.execute(query, values)

    def archive_project(self, project_id: int) -> None:
        """Archive a project."""
        self.update_project(project_id, {"is_archived": True})

    def add_page(self, page: Page) -> int:
        """Add a new page to a project."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO pages (project_id, url, title, parent_id, is_selected, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    page.project_id,
                    page.url,
                    page.title,
                    page.parent_id,
                    1 if page.is_selected else 0,
                    page.created_at.isoformat(),
                    page.updated_at.isoformat(),
                ),
            )
            return cast(int, cursor.lastrowid)

    def get_page(self, page_id: int) -> Page | None:
        """Retrieve a single page by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
            if row:
                return self._row_to_page(row)
        return None

    def get_project_pages(self, project_id: int) -> list[Page]:
        """Retrieve all pages for a given project."""
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM pages WHERE project_id = ? ORDER BY id", (project_id,)).fetchall()
            return [self._row_to_page(row) for row in rows]

    def update_page(self, page_id: int, updates: PageUpdate) -> None:
        """Update page details."""
        if not updates:
            return

        updated_at = datetime.now(UTC).isoformat()
        fields = []
        values = []
        for key, value in updates.items():
            fields.append(f"{key} = ?")
            values.append(1 if key == "is_selected" and isinstance(value, bool) else value)

        values.extend([updated_at, page_id])
        query = f"UPDATE pages SET {', '.join(fields)}, updated_at = ? WHERE id = ?"
        with self._get_connection() as conn:
            conn.execute(query, values)

    def update_page_selection(self, page_id: int, is_selected: bool, recursive: bool = False) -> None:
        """Update is_selected status for a page and optionally its children."""
        status = 1 if is_selected else 0
        updated_at = datetime.now(UTC).isoformat()

        with self._get_connection() as conn:
            if recursive:
                # Use a recursive CTE to find all children and grandchildren
                conn.execute(
                    """
                    WITH RECURSIVE children AS (
                        SELECT id FROM pages WHERE id = ?
                        UNION ALL
                        SELECT p.id FROM pages p
                        JOIN children c ON p.parent_id = c.id
                    )
                    UPDATE pages SET is_selected = ?, updated_at = ?
                    WHERE id IN (SELECT id FROM children)
                """,
                    (page_id, status, updated_at),
                )
            else:
                conn.execute(
                    "UPDATE pages SET is_selected = ?, updated_at = ? WHERE id = ?", (status, updated_at, page_id)
                )

    def _row_to_project(self, row: sqlite3.Row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            root_url=row["root_url"],
            status=row["status"],
            is_archived=bool(row["is_archived"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_page(self, row: sqlite3.Row) -> Page:
        return Page(
            id=row["id"],
            project_id=row["project_id"],
            url=row["url"],
            title=row["title"],
            parent_id=row["parent_id"],
            is_selected=bool(row["is_selected"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
