# editor/ui/components/tree.py
from typing import Optional

from textual.binding import Binding
from textual.widgets import Tree
from textual.widgets.tree import TreeNode


class NavigableTree(Tree):
    """Custom Tree supporting modal j/k vertical movement and h/l accordion jumping."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("h", "prev_category", "Prev Category/Parent", show=True),
        Binding("l", "next_category", "Next Category/Child", show=True),
    ]

    def jump_to_block_id(self, target_id: int) -> bool:
        """Expands, highlights and scrolls to the AST block node with this index.

        Moves the cursor only (no NodeSelected message); the caller is responsible
        for selecting the block, which keeps behaviour deterministic.
        """

        def find(node: TreeNode) -> Optional[TreeNode]:
            data = node.data
            if isinstance(data, int) and not isinstance(data, bool) and data == target_id:
                return node
            for child in node.children:
                hit = find(child)
                if hit:
                    return hit
            return None

        target = find(self.root)
        if target is None:
            return False

        ancestor = target.parent
        while ancestor:
            ancestor.expand()
            ancestor = ancestor.parent

        # Line numbers are only valid after the expanded tree has been re-laid out.
        def _reveal() -> None:
            self.move_cursor(target)
            self.scroll_to_node(target)

        self.call_after_refresh(_reveal)
        self.focus()
        return True

    def action_prev_category(self) -> None:
        node = self.cursor_node
        if not node:
            return
        if node.is_expanded and node.children:
            node.collapse()
            return
        if node.parent and node.parent != self.root:
            self.select_node(node.parent)
        elif node.parent == self.root:
            children = self.root.children
            idx = children.index(node)
            if idx > 0:
                self.select_node(children[idx - 1])

    def action_next_category(self) -> None:
        """Mirror of `h`: expand -> first child -> next sibling (top level included)."""
        node = self.cursor_node
        if not node:
            return
        # h: expanded with children -> collapse   |   l: collapsed with children -> expand
        if node.children and not node.is_expanded:
            node.expand()
            return
        # h: go to parent   |   l: go to first child
        if node.children and node.is_expanded:
            self.select_node(node.children[0])
            return
        # h: top-level node -> previous sibling   |   l: leaf -> next sibling
        siblings = node.parent.children if node.parent else []
        if node in siblings:
            idx = siblings.index(node)
            if idx < len(siblings) - 1:
                self.select_node(siblings[idx + 1])
