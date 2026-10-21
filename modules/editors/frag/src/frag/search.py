"""Snippet search: find which function/class contains a snippet and select that block.

Smart-case like Vim: an all-lowercase query is case-insensitive, otherwise case-sensitive.
Wrap the query in slashes (/re/) to use a regular expression.
Each hit maps to the INNERMOST function (else class, else any block) containing the match.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


@dataclass
class Hit:
    block_index: int
    block_type: str
    block_name: str
    line: int      # 1-indexed line in the file
    col: int       # 0-indexed column of the match on that line
    length: int


def compile_query(query: str) -> "re.Pattern":
    if len(query) > 2 and query.startswith("/") and query.endswith("/"):
        return re.compile(query[1:-1], 0 if any(c.isupper() for c in query) else re.IGNORECASE)
    return re.compile(re.escape(query), re.IGNORECASE if query == query.lower() else 0)


def _innermost(blocks: Sequence, line: int):
    inside = [b for b in blocks if b.start_line <= line <= b.end_line]
    return min(inside, key=lambda b: b.end_line - b.start_line) if inside else None


def find_hits(code: str, blocks: Sequence, query: str) -> Tuple[List[Hit], int]:
    """Returns (hits, matches_outside_any_block). One hit per block (its first match)."""
    rx = compile_query(query)
    real = [b for b in blocks if b.index != 0 and not b.name.startswith("Window L")]
    defs = [b for b in real if b.block_type in ("function", "class")]
    others = [b for b in real if b.block_type in ("variable", "statement", "binding")]
    hits: List[Hit] = []
    seen = set()
    outside = 0
    for ln, text in enumerate(code.splitlines(), 1):
        m = rx.search(text)
        if not m:
            continue
        blk = _innermost([b for b in defs if b.block_type == "function"], ln) \
            or _innermost([b for b in defs if b.block_type == "class"], ln) \
            or _innermost(others, ln)
        if blk is None:
            outside += 1
            continue
        if blk.index in seen:
            continue
        seen.add(blk.index)
        hits.append(Hit(blk.index, blk.block_type, blk.name, ln, m.start(), max(1, m.end() - m.start())))
    return hits, outside
