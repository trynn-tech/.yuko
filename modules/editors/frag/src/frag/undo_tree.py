"""Vim-style undo tree for whole-file history.

Mirrors how Vim models history: every committed change is an immutable *state*
(a node with a sequence number, a parent, and a timestamp). Undoing and then
editing never destroys anything, it forks a new branch. Python strings are
immutable and shared, so keeping a full snapshot per node is cheap and makes
checkout O(1): no patches to replay, exactly like Vim swapping a saved block back in.

Navigation primitives (all return the node moved to, or None if there was nowhere to go):
    undo() / redo()        walk the tree (redo follows the branch you last used)
    earlier(n) / later(n)  walk by *time* (Vim's g- / g+), crossing branches
    goto(seq)              jump to any state
"""

import difflib
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


def line_stats(old: str, new: str) -> Tuple[int, int]:
    """(lines_added, lines_removed) between two texts."""
    a, b = old.splitlines(), new.splitlines()
    added = removed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return added, removed


@dataclass(eq=False)
class UndoNode:
    seq: int
    text: str
    label: str
    timestamp: float
    parent: Optional["UndoNode"] = field(default=None, repr=False)
    children: List["UndoNode"] = field(default_factory=list, repr=False)
    redo_child: Optional["UndoNode"] = field(default=None, repr=False)
    _stats: Optional[Tuple[int, int]] = field(default=None, repr=False)

    @property
    def stats(self) -> Tuple[int, int]:
        """(added, removed) lines relative to the parent state (cached)."""
        if self._stats is None:
            self._stats = (0, 0) if self.parent is None else line_stats(self.parent.text, self.text)
        return self._stats


class UndoTree:
    def __init__(self, text: str, label: str = "Original", clock: Callable[[], float] = time.time):
        self._clock = clock
        self.root = UndoNode(seq=0, text=text, label=label, timestamp=clock())
        self.nodes: Dict[int, UndoNode] = {0: self.root}
        self.current: UndoNode = self.root

    @property
    def size(self) -> int:
        return len(self.nodes)

    # --- recording -----------------------------------------------------

    def commit(self, text: str, label: str) -> Optional[UndoNode]:
        """Records a new state as a child of the current one. No-op if text is unchanged."""
        if text == self.current.text:
            return None
        node = UndoNode(seq=len(self.nodes), text=text, label=label, timestamp=self._clock(), parent=self.current)
        self.current.children.append(node)
        self.current.redo_child = node
        self.nodes[node.seq] = node
        self.current = node
        return node

    # --- navigation ----------------------------------------------------

    def undo(self) -> Optional[UndoNode]:
        cur = self.current
        if cur.parent is None:
            return None
        cur.parent.redo_child = cur  # remember which branch we left, so redo returns to it
        self.current = cur.parent
        return self.current

    def redo(self) -> Optional[UndoNode]:
        nxt = self.current.redo_child or (self.current.children[-1] if self.current.children else None)
        if nxt is None:
            return None
        self.current = nxt
        return nxt

    def goto(self, seq: int) -> Optional[UndoNode]:
        node = self.nodes.get(seq)
        if node is None:
            return None
        walker = node
        while walker.parent is not None:  # make redo follow the path we just took
            walker.parent.redo_child = walker
            walker = walker.parent
        self.current = node
        return node

    def earlier(self, steps: int = 1) -> Optional[UndoNode]:
        """g-: previous state *in time*, regardless of branch."""
        target = max(0, self.current.seq - max(1, steps))
        return None if target == self.current.seq else self.goto(target)

    def later(self, steps: int = 1) -> Optional[UndoNode]:
        """g+: next state *in time*, regardless of branch."""
        target = min(len(self.nodes) - 1, self.current.seq + max(1, steps))
        return None if target == self.current.seq else self.goto(target)

    # --- inspection ----------------------------------------------------

    def path_to_root(self, node: Optional[UndoNode] = None) -> List[UndoNode]:
        node = node or self.current
        path = []
        while node is not None:
            path.append(node)
            node = node.parent
        return path

    def diff(self, from_seq: int, to_seq: int, filename: str = "file") -> str:
        a, b = self.nodes[from_seq], self.nodes[to_seq]
        return "".join(
            difflib.unified_diff(
                a.text.splitlines(keepends=True),
                b.text.splitlines(keepends=True),
                fromfile=f"{filename}@{a.seq}",
                tofile=f"{filename}@{b.seq}",
            )
        )


# ---------------------------------------------------------------------------
# ASCII graph layout (newest at the top), in the spirit of jiaoshijie/undotree
# ---------------------------------------------------------------------------

@dataclass
class GraphRow:
    seq: Optional[int]  # None for connector rows (branch merges)
    graph: str          # lane art, e.g. "| *   "; nodes are drawn as '*'
    node_col: int = -1  # column of the node glyph (-1 for connector rows)


def layout_graph(tree: UndoTree) -> List[GraphRow]:
    """Lays the tree out as rows of lane art, newest state first.

    * The branch that holds the most recent edit stays in lane 0 (the trunk).
    * Every other branch gets the lowest free lane to the right and merges back with
      '/' (or '\\') on the row under its first node.
    * One node per row; connector rows are separate (seq=None) so a UI can skip them.
    """
    nodes = tree.nodes
    # children always have a larger seq than their parent, so one descending pass suffices
    sub_max = {s: s for s in nodes}
    for s in sorted(nodes, reverse=True):
        p = nodes[s].parent
        if p is not None and sub_max[s] > sub_max[p.seq]:
            sub_max[p.seq] = sub_max[s]
    cont = {s: max(n.children, key=lambda c: sub_max[c.seq]).seq for s, n in nodes.items() if n.children}

    order = sorted(nodes, reverse=True)
    row_of = {seq: i for i, seq in enumerate(order)}

    chains: Dict[int, List[int]] = {}  # base seq -> members (base .. tip)
    chain_of: Dict[int, int] = {}
    for s in sorted(nodes):
        n = nodes[s]
        if n.parent is None or cont[n.parent.seq] != s:
            chains[s] = [s]
            chain_of[s] = s
        else:
            chains[chain_of[n.parent.seq]].append(s)
            chain_of[s] = chain_of[n.parent.seq]
    span = {cid: (row_of[m[-1]], row_of[cid]) for cid, m in chains.items()}  # (tip row, base row)

    lanes: List[List[Tuple[int, int]]] = []
    lane_of_chain: Dict[int, int] = {}
    for cid in sorted(chains, key=lambda c: span[c][0]):
        top, bottom = span[cid]
        for li, taken in enumerate(lanes):
            if all(bottom < t or top > b for t, b in taken):
                taken.append((top, bottom))
                lane_of_chain[cid] = li
                break
        else:
            lanes.append([(top, bottom)])
            lane_of_chain[cid] = len(lanes) - 1

    n_lanes = len(lanes)
    width = 2 * n_lanes

    def active(lane: int, row: int) -> bool:
        return any(t <= row <= b for t, b in lanes[lane])

    rows: List[GraphRow] = []
    for r, seq in enumerate(order):
        lane = lane_of_chain[chain_of[seq]]
        cells = [" "] * width
        for l in range(n_lanes):
            if l == lane:
                cells[2 * l] = "*"
            elif active(l, r):
                cells[2 * l] = "|"
        rows.append(GraphRow(seq, "".join(cells), 2 * lane))

        node = nodes[seq]
        if chain_of[seq] == seq and node.parent is not None:  # chain base: merge into the parent lane
            lp = lane_of_chain[chain_of[node.parent.seq]]
            conn = [" "] * width
            for l in range(n_lanes):
                if l != lane and active(l, r) and active(l, r + 1):
                    conn[2 * l] = "|"
            if lane > lp:
                for c in range(2 * lp + 1, 2 * lane - 1):
                    if conn[c] == " ":
                        conn[c] = "-"
                conn[2 * lane - 1] = "/"
            else:
                conn[2 * lane + 1] = "\\"
                for c in range(2 * lane + 2, 2 * lp):
                    if conn[c] == " ":
                        conn[c] = "-"
            rows.append(GraphRow(None, "".join(conn), -1))
    return rows
