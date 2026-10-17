"""Search strategy: `/snippet` or `:find snippet` selects the function that contains it.

n / N (or :find with no argument) cycle through the matching functions. One hit per
function/class (its first match); the cursor lands on the match inside the active buffer.
"""

import sys
from pathlib import Path
from typing import List

from rich.markup import escape

try:
    from ...search import Hit, find_hits
    from ..base import BaseEditorStrategy
except (ImportError, ValueError):
    for _parent in Path(__file__).resolve().parents:
        if (_parent / "editor" / "modular_editor.py").exists():
            if str(_parent) not in sys.path:
                sys.path.insert(0, str(_parent))
            break
    from editor.search import Hit, find_hits
    from editor.ui.base import BaseEditorStrategy


class SearchStrategy(BaseEditorStrategy):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.query: str = ""
        self.hits: List[Hit] = []
        self.pos: int = -1

    def find(self, query: str) -> bool:
        query = query.strip()
        if not query:  # `:find` alone repeats the last search
            return self.step(1) if self.hits else self._err("E35: No previous search pattern")
        try:
            hits, outside = find_hits(self.editor.raw_code, self.editor.blocks, query)
        except Exception as e:  # bad regex
            return self._err(f"E486: Invalid pattern: {e}")
        self.query, self.hits, self.pos = query, hits, -1
        if not hits:
            extra = f" ({outside} match(es) outside any function)" if outside else ""
            return self._err(f"E486: Pattern not found: {query}{extra}")

        # start at the first hit at/after the selected block (wrapping), like Vim's search from the cursor
        sel = next((b for b in self.editor.blocks if b.index == self.app.selected_block_id), None)
        start_line = sel.start_line if sel is not None and sel.index != 0 else 0
        first = next((i for i, h in enumerate(hits) if h.line >= start_line), 0)
        return self._goto(first)

    def step(self, delta: int) -> bool:
        if not self.hits:
            return self._err("E35: No previous search pattern (use / or :find)")
        return self._goto((self.pos + delta) % len(self.hits))

    def _goto(self, i: int) -> bool:
        hit = self.hits[i]
        self.pos = i
        nav = self.app.navigation_strategy
        if not nav._focus_block(hit.block_index):
            return False
        block = next((b for b in self.editor.blocks if b.index == hit.block_index), None)
        area = self.app.query_one("#content-input")
        if block is not None:
            try:
                from textual.widgets.text_area import Selection
                row = hit.line - block.start_line
                area.selection = Selection(start=(row, hit.col), end=(row, hit.col + hit.length))  # highlights the match
            except Exception:
                pass
        self.app.log_status(
            f"[bold #00d7ff]/{escape(self.query)}[/bold #00d7ff]  \\[{i + 1}/{len(self.hits)}] "
            f"in {hit.block_type} [bold]{escape(hit.block_name)}[/bold] (L{hit.line})   n / N = next / prev"
        )
        return True

    def _err(self, msg: str) -> bool:
        self.app.log_status(f"[bold #ff5555]{escape(msg)}[/bold #ff5555]")
        return False
