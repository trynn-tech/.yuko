# editor/ui/components/tree.py
from typing import Optional
from textual.binding import Binding
from textual.widgets import Tree


class NavigableTree(Tree):
    """Custom Tree supporting modal j/k vertical movement and h/l accordion jumping."""

    BINDINGS = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("h", "prev_category", "Prev Category/Parent", show=True),
        Binding("l", "next_category", "Next Category/Child", show=True),
    ]

    def jump_to_block_id(self, target_id: int) -> bool:
        """Finds, expands, highlights, and scrolls to a block by its identifier.
        
        Returns True if a match was successfully found and focused.
        """
        def find_block_node(parent_node) -> Optional[Tree]:
            if hasattr(parent_node, "data") and parent_node.data == target_id:
                return parent_node
                
            if str(parent_node.label).strip().endswith(str(target_id)):
                return parent_node
                
            for child in parent_node.children:
                result = find_block_node(child)
                if result:
                    return result
            return None

        target_node = find_block_node(self.root)

        if target_node:
            # Expand lineage from target up to the root container path
            current = target_node.parent
            while current:
                current.expand()
                current = current.parent
                
            # Perform selection and invoke viewport scrolling safely on self
            self.select_node(target_node)
            self.scroll_to_node(target_node)
            self.focus()
            return True
            
        return False

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
        node = self.cursor_node
        if not node:
            return
        if node.children and not node.is_expanded:
            node.expand()
            if node.children:
                self.select_node(node.children[0])
            return
        elif node.parent and node.parent != self.root:
            parent_children = node.parent.children
            idx = parent_children.index(node)
            if idx < len(parent_children) - 1:
                self.select_node(parent_children[idx + 1])

