import sqlite3
from pathlib import Path

import pytest

from docs2pdf.database import DatabaseManager, Page, Project


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test_docs2pdf.db"


@pytest.fixture
def db_manager(db_path: Path) -> DatabaseManager:
    manager = DatabaseManager(db_path)
    manager.initialize()
    return manager


def test_pages_table_exists(db_path: Path):
    manager = DatabaseManager(db_path)
    manager.initialize()
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pages'")
        assert cursor.fetchone() is not None


def test_add_and_get_pages(db_manager: DatabaseManager):
    project_id = db_manager.add_project(Project(name="Test", root_url="url"))

    page1 = Page(project_id=project_id, url="url/1", title="Page 1", is_selected=True)
    page1_id = db_manager.add_page(page1)

    page2 = Page(project_id=project_id, url="url/1/1", title="Page 1.1", parent_id=page1_id)
    db_manager.add_page(page2)

    pages = db_manager.get_project_pages(project_id)
    assert len(pages) == 2
    assert pages[0].title == "Page 1"
    assert pages[1].parent_id == page1_id


def test_update_page_selection(db_manager: DatabaseManager):
    project_id = db_manager.add_project(Project(name="Test", root_url="url"))
    page_id = db_manager.add_page(Page(project_id=project_id, url="url/1", title="Page 1"))

    db_manager.update_page_selection(page_id, False)
    page = db_manager.get_page(page_id)
    assert page.is_selected is False

    db_manager.update_page_selection(page_id, True)
    page = db_manager.get_page(page_id)
    assert page.is_selected is True


def test_update_page_selection_recursive(db_manager: DatabaseManager):
    project_id = db_manager.add_project(Project(name="Test", root_url="url"))
    p_id = db_manager.add_page(Page(project_id=project_id, url="url/p", title="Parent"))
    c_id = db_manager.add_page(Page(project_id=project_id, url="url/p/c", title="Child", parent_id=p_id))
    gc_id = db_manager.add_page(Page(project_id=project_id, url="url/p/c/gc", title="Grandchild", parent_id=c_id))

    # Deselect parent recursively
    db_manager.update_page_selection(p_id, False, recursive=True)

    assert db_manager.get_page(p_id).is_selected is False
    assert db_manager.get_page(c_id).is_selected is False
    assert db_manager.get_page(gc_id).is_selected is False


def test_delete_project_pages(db_manager: DatabaseManager):
    project_id = db_manager.add_project(Project(name="Test Delete", root_url="url"))
    db_manager.add_page(Page(project_id=project_id, url="url/1", title="Page 1"))
    db_manager.add_page(Page(project_id=project_id, url="url/2", title="Page 2"))

    assert len(db_manager.get_project_pages(project_id)) == 2

    db_manager.delete_project_pages(project_id)

    assert len(db_manager.get_project_pages(project_id)) == 0
