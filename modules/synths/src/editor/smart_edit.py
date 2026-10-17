"""Smart edit: paste several functions/classes and have them matched to the file.

split_snippet()  breaks the input into top-level parts (functions, classes, imports, assignments)
plan_edits()     matches each part to an existing block by name and scope, deciding:
                   replace       same-named function/class/variable exists  (decorators included)
                   unchanged     identical to what is already there
                   insert_after  new definition, placed right after the previous matched part
                   insert_before ... or before the next matched part, else at the end of the file
                   error         ambiguous name or overlapping targets
apply_plan()     queues the plan on the editor as one batch (one undo state)

Python snippets are parsed with `ast`; other languages fall back to a single part.
"""

import ast
import difflib
import re
import textwrap
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

IMPORT_RX = re.compile(r"^\s*(import\s+|from\s+\S+\s+import\s+)")


@dataclass
class Part:
    kind: str   # function | class | import | assign | other
    name: str
    text: str   # dedented source, decorators included


@dataclass
class PlannedEdit:
    action: str            # replace | insert_after | insert_before | unchanged | error
    label: str
    note: str = ""
    start_line: int = 0    # target/anchor range in the file (1-indexed, inclusive)
    end_line: int = 0
    text: str = ""         # final text, already re-indented
    added: int = 0
    removed: int = 0

    @property
    def applies(self) -> bool:
        return self.action in ("replace", "insert_after", "insert_before")


def _stats(old: str, new: str) -> Tuple[int, int]:
    added = removed = 0
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old.splitlines(), new.splitlines(), autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return added, removed


def _norm(t: str) -> str:
    return "\n".join(l.rstrip() for l in t.splitlines()).strip("\n")


def _reindent(text: str, indent: str) -> str:
    return "\n".join((indent + l) if l.strip() else l for l in text.splitlines())


# ---------------------------------------------------------------------------
# 1. split
# ---------------------------------------------------------------------------

def split_snippet(snippet: str, python: bool = True) -> Tuple[List[Part], str, Optional[str]]:
    """Returns (parts, original_indent, error)."""
    if not snippet.strip():
        return [], "", None
    src = textwrap.dedent(snippet).strip("\n")
    first = next(l for l in snippet.splitlines() if l.strip())
    first_d = next(l for l in src.splitlines() if l.strip())
    indent = first[: len(first) - len(first_d)]
    if not python:
        return [Part("other", "", src)], indent, None
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return [], indent, f"SyntaxError (line {e.lineno}): {e.msg}"
    lines = src.splitlines()
    parts: List[Part] = []
    for node in tree.body:
        start = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        text = "\n".join(lines[start - 1: node.end_lineno])
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            parts.append(Part("function", node.name, text))
        elif isinstance(node, ast.ClassDef):
            parts.append(Part("class", node.name, text))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            parts.append(Part("import", text, text))
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            parts.append(Part("assign", ast.unparse(node.targets[0]), text))
        elif isinstance(node, ast.AnnAssign):
            parts.append(Part("assign", ast.unparse(node.target), text))
        else:
            parts.append(Part("other", "", text))
    return parts, indent, None


# ---------------------------------------------------------------------------
# 2. plan
# ---------------------------------------------------------------------------

def plan_edits(code: str, blocks: Sequence, snippet: str, selected_index: Optional[int] = None,
               python: bool = True) -> Tuple[List[PlannedEdit], Optional[str]]:
    parts, p_indent, err = split_snippet(snippet, python)
    if err or not parts:
        return [], err
    lines = code.splitlines()
    real = [b for b in blocks if b.index != 0 and not b.name.startswith("Window L")]
    sel = next((b for b in real if b.index == selected_index), None)

    def ind(b) -> str:
        ln = lines[b.start_line - 1] if 0 < b.start_line <= len(lines) else ""
        return ln[: len(ln) - len(ln.lstrip())]

    def deco_start(b) -> int:
        s = b.start_line
        while s > 1 and lines[s - 2].lstrip().startswith("@") and lines[s - 2][: len(ind(b))].strip() == "":
            s -= 1
        return s

    btype = {"function": "function", "class": "class", "assign": "variable"}

    def match(part: Part):
        """-> (block | None, error | None)"""
        if part.kind not in btype:
            return None, None
        same = [b for b in real if b.block_type == btype[part.kind] and b.name == part.name]
        exact = [b for b in same if ind(b) == p_indent]
        cands = exact or (same if p_indent else [b for b in same if ind(b) == ""])
        if len(cands) > 1 and sel is not None:
            inside = [b for b in cands if sel.start_line <= b.start_line and b.end_line <= sel.end_line]
            cands = inside or cands
        if len(cands) > 1:
            return None, f"ambiguous: {part.name} matches " + ", ".join(f"[{b.index}]" for b in cands) + " (select the class/function it belongs to first)"
        return (cands[0] if cands else None), None

    plan: List[PlannedEdit] = []
    resolved: List[Optional[Tuple[int, int]]] = []   # (start,end) range each part resolved to, else None
    top = [b for b in real if ind(b) == ""]
    eof = max([b.end_line for b in top] + [len(lines)])

    only_other = len(parts) == 1 and parts[0].kind == "other"
    for part in parts:
        label = f"{part.kind} {part.name}".strip() if part.kind != "import" else "import"
        if part.kind == "import":
            if any(l.strip() == part.text.strip() for l in lines):
                plan.append(PlannedEdit("unchanged", label, "already present")); resolved.append(None); continue
        if only_other and sel is not None:
            s, e = deco_start(sel), sel.end_line
            new = _reindent(part.text, ind(sel))
            a, d = _stats("\n".join(lines[s - 1:e]), new)
            plan.append(PlannedEdit("replace", f"selected [{sel.index}] {sel.name}", "no definition found: replaces the selected block", s, e, new, a, d))
            resolved.append((s, e)); continue

        blk, amb = match(part)
        if amb:
            plan.append(PlannedEdit("error", label, amb)); resolved.append(None); continue
        if blk is not None:
            s, e = deco_start(blk), blk.end_line
            new = _reindent(part.text, ind(blk))
            old = "\n".join(lines[s - 1:e])
            if _norm(old) == _norm(new):
                plan.append(PlannedEdit("unchanged", f"{label} [{blk.index}]", "identical", s, e)); resolved.append((s, e)); continue
            a, d = _stats(old, new)
            plan.append(PlannedEdit("replace", f"{label} [{blk.index}]", "", s, e, new, a, d))
            resolved.append((s, e)); continue
        plan.append(PlannedEdit("insert_after", label, "new"))  # anchor decided below
        resolved.append(None)

    # --- place inserts relative to their resolved neighbours, coalescing runs -----
    ordered: List[PlannedEdit] = []
    i = 0
    while i < len(plan):
        pe = plan[i]
        if pe.action != "insert_after" or pe.note != "new":
            ordered.append(pe); i += 1; continue
        j = i
        while j < len(plan) and plan[j].action == "insert_after" and plan[j].note == "new":
            j += 1
        run = list(range(i, j))
        prev_r = next((resolved[k] for k in range(i - 1, -1, -1) if resolved[k]), None)
        next_r = next((resolved[k] for k in range(j, len(plan)) if resolved[k]), None)
        texts = [_reindent(parts[k].text, p_indent) for k in run]
        deflike = any(parts[k].kind in ("function", "class") for k in run)
        gap = (1 if p_indent else 2) if deflike else 0
        joined = ("\n" * gap).join(texts) if deflike else "\n".join(texts)
        names = ", ".join(plan[k].label for k in run)
        a, _ = _stats("", joined)
        if prev_r:
            ordered.append(PlannedEdit("insert_after", names, "after previous match", prev_r[1], prev_r[1], "\n" * gap + joined, a, 0))
        elif next_r:
            ordered.append(PlannedEdit("insert_before", names, "before next match", next_r[0], next_r[0], joined + "\n" * (gap + 1), a, 0))
        else:
            anchor = sel.end_line if (sel is not None and p_indent) else eof
            ordered.append(PlannedEdit("insert_after", names, "end of file" if anchor == eof else "after selection", anchor, anchor, "\n" * gap + joined, a, 0))
        i = j

    # --- overlapping targets cannot be applied in one batch ---------------------------
    taken: List[Tuple[int, int]] = []
    for pe in ordered:
        if pe.action == "replace":
            if any(not (pe.end_line < s or pe.start_line > e) for s, e in taken):
                pe.action, pe.note = "error", "overlaps another replacement (a class and one of its methods?)"
            else:
                taken.append((pe.start_line, pe.end_line))
    return ordered, None


# ---------------------------------------------------------------------------
# 3. apply
# ---------------------------------------------------------------------------

def plan_label(plan: Sequence[PlannedEdit]) -> str:
    rep = [p.label.split(" [")[0].replace("function ", "").replace("class ", "") for p in plan if p.action == "replace"]
    ins = [p.label for p in plan if p.action.startswith("insert")]
    bits = []
    if rep:
        bits.append("replace " + ", ".join(rep[:3]) + (f" (+{len(rep) - 3})" if len(rep) > 3 else ""))
    if ins:
        bits.append("insert " + ", ".join(ins[:2]))
    return "smart edit: " + "; ".join(bits) if bits else "smart edit"


def apply_plan(editor, plan: Sequence[PlannedEdit]) -> int:
    """Queues every applicable edit on `editor` using explicit line ranges. Returns how many."""
    try:
        from ..modular_editor import CodeBlock  # type: ignore
    except (ImportError, ValueError):
        from editor.modular_editor import CodeBlock
    editor.mutation_buffer.clear()
    n = 0
    # apply_batch sorts by start line only (bottom-up) and keeps queue order for ties, so queue
    # insert_after first, then replace, then insert_before: each tie then leaves the others' lines intact.
    rank = {"insert_after": 0, "replace": 1, "insert_before": 2}
    for pe in sorted((p for p in plan if p.applies), key=lambda p: rank[p.action]):
        idx = len(editor.blocks)  # synthetic range block; the next parse_document() discards it
        editor.blocks.append(CodeBlock(index=idx, block_type="statement", name="smart-range",
                                       start_line=pe.start_line, end_line=pe.end_line, content=""))
        editor.queue_mutation(pe.action, [idx], pe.text)
        n += 1
    return n
