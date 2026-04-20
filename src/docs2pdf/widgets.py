from typing import TypeVar
from textual.widgets import Tree
from textual.widgets.tree import TreeNode
from textual.style import Style
from rich.text import Text
from typing import TypeVar, Any, cast

T = TypeVar("T")

class CheckboxTree(Tree[Any]):
    """
    A Tree widget that supports recursive checkbox selection.
    Data associated with nodes must be dict-like or have an 'is_selected' attribute.
    """

    def render_label(self, node: TreeNode[Any], base_style: Style, style: Style) -> Text: # type: ignore[override]
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
            setattr(data, "is_selected", state)

        for child in node.children:
            self._recursive_set(child, state)

