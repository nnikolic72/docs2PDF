import sqlite3
from pathlib import Path

import pytest

from docs2pdf.database import DatabaseManager, Project


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Fixture to provide a temporary database path."""
    return tmp_path / "test_docs2pdf.db"


@pytest.fixture
def db_manager(db_path: Path) -> DatabaseManager:
    """Fixture to provide a DatabaseManager instance."""
    manager = DatabaseManager(db_path)
    manager.initialize()
    return manager


def test_initialize_creates_table(db_path: Path):
    """Test that initialize creates the projects table."""
    manager = DatabaseManager(db_path)
    manager.initialize()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='projects'")
        assert cursor.fetchone() is not None


def test_add_project(db_manager: DatabaseManager):
    """Test adding a new project."""
    project = Project(name="Test Project", root_url="https://example.com/docs")
    project_id = db_manager.add_project(project)

    assert project_id is not None

    saved_project = db_manager.get_project(project_id)
    assert saved_project is not None
    assert saved_project.name == "Test Project"
    assert saved_project.root_url == "https://example.com/docs"
    assert saved_project.status == "pending"
    assert saved_project.is_archived is False


def test_get_all_projects(db_manager: DatabaseManager):
    """Test retrieving all non-archived projects."""
    db_manager.add_project(Project(name="P1", root_url="url1"))
    db_manager.add_project(Project(name="P2", root_url="url2", is_archived=True))

    projects = db_manager.get_all_projects(include_archived=False)
    assert len(projects) == 1
    assert projects[0].name == "P1"

    all_projects = db_manager.get_all_projects(include_archived=True)
    assert len(all_projects) == 2


def test_update_project(db_manager: DatabaseManager):
    """Test updating project details."""
    project_id = db_manager.add_project(Project(name="Old Name", root_url="old_url"))

    db_manager.update_project(project_id, {"name": "New Name", "status": "completed"})

    updated = db_manager.get_project(project_id)
    assert updated.name == "New Name"
    assert updated.status == "completed"


def test_archive_project(db_manager: DatabaseManager):
    """Test archiving a project."""
    project_id = db_manager.add_project(Project(name="To Archive", root_url="url"))

    db_manager.archive_project(project_id)

    project = db_manager.get_project(project_id)
    assert project.is_archived is True
