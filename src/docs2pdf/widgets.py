from typing import Any, TypeVar, cast

from rich.spinner import Spinner
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.style import Style
from textual.widgets import Label, Static, Tree
from textual.widgets.tree import TreeNode

T = TypeVar("T")


class CheckboxTree(Tree[Any]):
    """
    A Tree widget that supports recursive checkbox selection.
    Data associated with nodes must be dict-like or have an 'is_selected' attribute.
    """

    def render_label(self, node: TreeNode[Any], base_style: Style, style: Style) -> Text:  # type: ignore[override]
        # Use data to store the 'selected' state
        data = node.data
        is_selected = False
        if isinstance(data, dict):
            is_selected = bool(cast(dict[Any, Any], data).get("is_selected", False))
        elif data is not None:
            is_selected = bool(getattr(data, "is_selected", False))

        icon = "☑" if is_selected else "☐"
        label = Text.from_markup(str(node.label))
        # Rich Text.stylize expects rich.style.Style. Textual.style.Style is compatible or can be converted.
        label.stylize(cast(Any, base_style))
        return Text.assemble(f"{icon} ", label)

    def toggle_node(self, node: TreeNode[T]) -> None:
        """Recursively toggle a node and all its children."""
        new_state = not self._get_node_selected(node)
        self._recursive_set(node, new_state)
        self.refresh()

    def _get_node_selected(self, node: TreeNode[T]) -> bool:
        data = node.data
        if isinstance(data, dict):
            return bool(cast(dict[Any, Any], data).get("is_selected", False))
        elif data is not None:
            return bool(getattr(data, "is_selected", False))
        return False

    def _recursive_set(self, node: TreeNode[T], state: bool) -> None:
        data = node.data
        if isinstance(data, dict):
            cast(dict[Any, Any], data)["is_selected"] = state
        elif data is not None:
            cast(Any, data).is_selected = state

        for child in node.children:
            self._recursive_set(child, state)


class DownloadRow(Horizontal):
    """A single row in the download progress list."""

    DEFAULT_CSS = """
    DownloadRow {
        height: 1;
        margin: 0;
        padding: 0;
    }
    DownloadRow Static {
        width: 3;
    }
    DownloadRow Label {
        margin-right: 1;
    }
    DownloadRow .success {
        color: $success;
        width: 3;
    }
    DownloadRow .error {
        color: $error;
        width: 3;
    }
    DownloadRow .url {
        width: 1fr;
    }
    """

    def __init__(self, url: str, status: str):
        super().__init__()
        self.url = url
        self.status = status

    def compose(self) -> ComposeResult:
        if self.status == "downloading":
            yield Static(Spinner("dots"))
        elif self.status == "done":
            yield Label("✔", classes="success")
        elif self.status == "error":
            yield Label("✘", classes="error")
        yield Label(self.url, classes="url")


class DownloadProgress(Vertical):
    """A widget to display download progress for multiple pages."""

    DEFAULT_CSS = """
    DownloadProgress {
        border: solid $accent;
        padding: 1;
        height: auto;
        min-height: 5;
        max-height: 15;
    }
    """

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.history: list[tuple[str, str]] = []  # (url, status)
        self.current_url: str | None = None

    def update_status(self, url: str, status: str) -> None:
        """Update the status of a URL and refresh the display."""
        if status == "downloading":
            self.current_url = url
        else:
            if self.current_url == url:
                self.current_url = None
            # Add to history, keep only last 10
            self.history.append((url, status))
            if len(self.history) > 10:
                self.history.pop(0)

        self._refresh_rows()

    def _refresh_rows(self) -> None:
        # Clear existing rows
        self.query(DownloadRow).remove()

        # Add history rows (last 10)
        for url, status in self.history:
            self.mount(DownloadRow(url, status))

        # Add current downloading row if any
        if self.current_url:
            self.mount(DownloadRow(self.current_url, "downloading"))
