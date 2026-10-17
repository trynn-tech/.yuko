"""Navigation strategy for single-file AST semantic breakdown and workspace directory exploration.

Workspace files carry spreadsheet-style alphabetical codes ([a] .. [z], [aa] .. [ab]).
Jump-input semantics:
  * digits  -> AST block index (single-file mode) / file index (workspace mode)
  * letters -> workspace file code (works in both modes)
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from rich.markup import escape
from textual.widgets.tree import TreeNode

try:
    # Normal package execution (python -m editor.ui.app, installed entrypoint, etc.)
    from ...modular_editor import ModularBlockEditor
    from ..base import NavigationStrategy
    from ..components.tree import NavigableTree
except (ImportError, ValueError):
    # Direct script / Nix execution: put the directory *containing* `editor/` on sys.path
    for _parent in Path(__file__).resolve().parents:
        if (_parent / "editor" / "modular_editor.py").exists():
            if str(_parent) not in sys.path:
                sys.path.insert(0, str(_parent))
            break
    from editor.modular_editor import ModularBlockEditor
    from editor.ui.base import NavigationStrategy
    from editor.ui.components.tree import NavigableTree

# Single source of truth: tree population and index lookup MUST skip the same entries,
# otherwise the [a]/[ab] labels drift away from the files they resolve to.
SKIP_NAMES = frozenset(
    {
        "__pycache__",
        "node_modules",
        "target",
        "result",
        ".git",
        ".pytest_cache",
        "venv",
        ".venv",
    }
)


WORKSPACE_EXPAND_DEPTH = 1  # workspace mode: folders this many levels below the root start unfolded


class DefaultNavigationStrategy(NavigationStrategy):
    """Single-file AST views plus workspace exploration.

    Workspace mode numbers files 1, 2, 3 ... and jumping there SELECTS the file (it stays selected,
    so `y` yanks it, Enter opens it). The Directory Explorer inside the AST view keeps letter codes
    (a, b ... aa) because plain numbers mean block indices there.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.directory_mode: bool = False
        self.fs_root_path: Optional[Path] = None
        self.workspace_selected: Optional[Path] = None     # persists across tree rebuilds
        self._fs_nodes: Dict[Path, TreeNode] = {}

    # ------------------------------------------------------------------
    # Spreadsheet-style base-26 helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _index_to_alpha(n: int) -> str:
        """1 -> a, 26 -> z, 27 -> aa, 28 -> ab."""
        if n < 1:
            return "a"
        result: List[str] = []
        while n > 0:
            n, rem = divmod(n - 1, 26)
            result.append(chr(97 + rem))
        return "".join(reversed(result))

    @staticmethod
    def _alpha_to_index(s: str) -> int:
        """a -> 1, z -> 26, aa -> 27. Returns -1 for invalid input."""
        s = s.strip().lower()
        if not s:
            return -1
        n = 0
        for ch in s:
            if not ("a" <= ch <= "z"):
                return -1
            n = n * 26 + (ord(ch) - ord("a") + 1)
        return n

    # ------------------------------------------------------------------
    # Workspace helpers
    # ------------------------------------------------------------------
    def set_filesystem_mode(self, directory_mode: bool, root_path: Optional[Path] = None) -> None:
        """Toggles Workspace Directory mode vs single-file AST mode.
        The workspace root is resolved once and then kept stable so file codes
        do not shift while you open files from sub-folders.
        """
        self.directory_mode = directory_mode
        if root_path is not None:
            self.fs_root_path = root_path.resolve()
        elif self.fs_root_path is None:
            fp = getattr(self.app, "filepath", None)
            if fp:
                p = Path(fp)
                self.fs_root_path = p.resolve() if p.is_dir() else p.parent.resolve()
            else:
                self.fs_root_path = Path.cwd().resolve()
        self.populate_tree()

    def _get_base_dir(self) -> Path:
        base = self.fs_root_path
        if base is None:
            fp = getattr(self.app, "filepath", None)
            if fp:
                p = Path(fp)
                base = p if p.is_dir() else p.parent
        if base is None or not base.exists():
            base = Path.cwd()
        return base.resolve()

    @staticmethod
    def _list_entries(dir_path: Path) -> List[os.DirEntry]:
        """Sorted (dirs first, then name), filtered entries. Shared by tree + index lookup."""
        try:
            with os.scandir(dir_path) as it:
                entries = sorted(it, key=lambda e: (not e.is_dir(follow_symlinks=False), e.name.lower()))
        except (PermissionError, FileNotFoundError, NotADirectoryError):
            return []
        return [e for e in entries if not e.name.startswith(".") and e.name not in SKIP_NAMES]

    def _collect_directory_files(self, dir_path: Path, file_list: List[Path]) -> None:
        """Files in the exact global order used by populate (so code 'a' == first file)."""
        for entry in self._list_entries(dir_path):
            if entry.is_dir(follow_symlinks=False):
                self._collect_directory_files(Path(entry.path), file_list)
            else:
                file_list.append(Path(entry.path))

    def _workspace_files(self) -> List[Path]:
        files: List[Path] = []
        self._collect_directory_files(self._get_base_dir(), files)
        return files

    # ------------------------------------------------------------------
    # Clipboard / yank
    # ------------------------------------------------------------------
    def _copy_text(self, text: str) -> bool:
        """Copies to the system clipboard (wl-copy / xclip / xsel), falling back to OSC52.
        Always mirrors into app.internal_yank_buffer so Vim `p` can paste it.
        """
        self.app.internal_yank_buffer = text
        for cmd in (
            ["wl-copy"],
            ["xclip", "-selection", "clipboard"],
            ["xsel", "--clipboard", "--input"],
        ):
            try:
                subprocess.run(
                    cmd,
                    input=text.encode("utf-8"),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                    check=True,
                )
                return True
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                continue
        try:
            self.app.copy_to_clipboard(text)  # OSC52 via Textual
            return True
        except Exception:
            return False

    def _yank_file_content(self, path: Path, label: str = "file contents") -> bool:
        """Reads full file contents and copies them to the system clipboard & internal buffer."""
        try:
            resolved_path = path.resolve()
            if not resolved_path.is_file():
                return False
            content = resolved_path.read_text(encoding="utf-8")
            self._copy_text(content)
            self.app.log_status(
                f"[bold #00ffaf]Yanked {escape(label)} ({escape(resolved_path.name)}) to clipboard & buffer![/bold #00ffaf]"
            )
            return True
        except Exception as e:
            self.app.log_status(f"[bold #ff5f5f]Failed to yank file contents:[/bold #ff5f5f] {escape(str(e))}")
            return False

    def yank_target(self, target: Any) -> bool:
        """Yanks file contents (for file nodes/codes) or AST block content."""
        try:
            if hasattr(target, "data"):  # TreeNode
                target = target.data
            if isinstance(target, dict):
                path = target.get("path")
                if path and Path(path).exists():
                    p = Path(path)
                    if p.is_file():
                        return self._yank_file_content(p)
                    else:
                        # If a directory is targeted, yank its path string representation
                        p_str = str(p.resolve())
                        self._copy_text(p_str)
                        self.app.log_status(f"[bold #00ffaf]Yanked directory path to clipboard:[/bold #00ffaf] {escape(p_str)}")
                        return True
                return False
            if isinstance(target, str):
                target = target.strip()
                if os.sep in target:  # explicit path string
                    p = Path(target).expanduser()
                    if p.is_file():
                        return self._yank_file_content(p)
                    return False
                if target.isdigit():
                    target = int(target)
                else:
                    idx = self._alpha_to_index(target)
                    return self._yank_file_index(idx) if idx > 0 else False
            if isinstance(target, int):
                if self.directory_mode:
                    return self._yank_file_index(target)
                block = next((b for b in self.editor.blocks if b.index == target), None)
                if block is None:
                    self.app.log_status(f"[bold #ff5f5f]No block [{target}] to yank.[/bold #ff5f5f]")
                    return False
                self._copy_text(block.content)
                self.app.log_status(f"[bold #00ffaf]Yanked Block [{target}] to clipboard & buffer.[/bold #00ffaf]")
                return True
        except Exception as e:
            self.app.log_status(f"[bold #ff5f5f]Yank failed:[/bold #ff5f5f] {escape(str(e))}")
        return False

    def _yank_file_index(self, n: int) -> bool:
        files = self._workspace_files()
        if 1 <= n <= len(files):
            return self._yank_file_content(files[n - 1], label=f"file [{self._index_to_alpha(n)}] contents")
        self.app.log_status(
            f"[bold #ff5f5f]File code [{self._index_to_alpha(n)}] out of range (1-{len(files)}).[/bold #ff5f5f]"
        )
        return False

    # ------------------------------------------------------------------
    # Anchors & jumping
    # ------------------------------------------------------------------
    def resolve_anchor(self, line_num: int) -> Optional[int]:
        """Returns the index of a block covering `line_num` (creating a ±3 window if supported)."""
        if hasattr(self.editor, "create_line_window_block"):
            block = self.editor.create_line_window_block(line_num, radius=3)
            if block is not None:
                self.populate_tree()
                return block.index  # create_line_window_block returns a CodeBlock, not an int
        matching = [
            b for b in self.editor.blocks
            if b.index != 0 and b.start_line <= line_num <= b.end_line
        ]
        if matching:
            return min(matching, key=lambda b: b.end_line - b.start_line).index
        return None

    def jump_to_block(self, target: Union[int, str, Any]) -> bool:
        """Digits: block index (AST mode) or file index (workspace mode). Letters: file code."""
        if hasattr(target, "data"):
            target = target.data
        if isinstance(target, dict):
            return self.select_block(target)
        code = str(target).strip()
        if not code:
            return False
        if code.isdigit():
            n = int(code)
            return self._open_file_by_index(n) if self.directory_mode else self._focus_block(n)
        n = self._alpha_to_index(code)
        if n < 1:
            self.app.log_status(f"[bold #ff5f5f]Invalid index '{escape(code)}'.[/bold #ff5f5f]")
            return False
        return self._open_file_by_index(n)

    def _focus_block(self, block_idx: int) -> bool:
        if not any(b.index == block_idx for b in self.editor.blocks):
            self.app.log_status(f"[bold #ff5f5f]Block ID {block_idx} not found.[/bold #ff5f5f]")
            return False
        try:
            self.app.query_one("#ast-tree", NavigableTree).jump_to_block_id(block_idx)
        except Exception:
            pass  # tree highlight is cosmetic; selection below is what matters
        return self.select_block(block_idx)

    def _open_file_by_index(self, n: int) -> bool:
        files = self._workspace_files()
        if 1 <= n <= len(files):
            if self.directory_mode:
                return self._select_workspace_file(files[n - 1], n)  # select + keep browsing
            return self.select_block({"type": "file", "path": files[n - 1]})
        label = str(n) if self.directory_mode else self._index_to_alpha(n)
        self.app.log_status(
            f"[bold #ff5f5f]File [{label}] out of range (1-{len(files)} files).[/bold #ff5f5f]"
        )
        return False

    def _reveal(self, path: Path) -> bool:
        node = self._fs_nodes.get(path)
        if node is None:
            return False
        tree = self.app.query_one("#ast-tree", NavigableTree)
        ancestor = node.parent
        while ancestor:
            ancestor.expand()
            ancestor = ancestor.parent

        def place() -> None:
            tree.move_cursor(node)
            tree.scroll_to_node(node)

        tree.call_after_refresh(place)  # line numbers are only valid after the re-layout
        return True

    def _select_workspace_file(self, path: Path, n: Optional[int] = None) -> bool:
        """Workspace-mode jump: highlight the file and remember it (so `y` can yank it)."""
        self.workspace_selected = path
        self._reveal(path)
        self.app.query_one("#ast-tree", NavigableTree).focus()
        tag = f"\\[{n}] " if n is not None else ""
        self.app.log_status(
            f"[bold #00ffaf]Selected[/bold #00ffaf] {tag}{escape(path.name)}   "
            f"[dim]y = yank contents · Enter = open · D = delete[/dim]"
        )
        return True

    def _restore_workspace_cursor(self) -> None:
        if self.directory_mode and self.workspace_selected is not None:
            self._reveal(self.workspace_selected)

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------
    def _populate_directory_node(self, parent_node: TreeNode, dir_path: Path, index_counter: List[int],
                                 numeric: bool = False, depth: int = 0) -> None:
        for entry in self._list_entries(dir_path):
            entry_path = Path(entry.path)
            if entry.is_dir(follow_symlinks=False):
                dir_node = parent_node.add(
                    f"📁 {escape(entry.name)}", expand=numeric and depth < WORKSPACE_EXPAND_DEPTH
                )
                dir_node.data = {"type": "directory", "path": entry_path}
                self._fs_nodes[entry_path] = dir_node
                self._populate_directory_node(dir_node, entry_path, index_counter, numeric, depth + 1)
            else:
                index_counter[0] += 1
                n = index_counter[0]
                alpha = str(n) if numeric else self._index_to_alpha(n)
                fp = getattr(self.app, "filepath", None)
                is_active = bool(fp) and entry_path.resolve() == Path(fp).resolve()
                icon = "🎯" if is_active else "📄"
                # "\[" escapes Rich markup, otherwise "[a]" is parsed as a style tag and vanishes
                leaf = parent_node.add_leaf(
                    f"\\[{alpha}] {icon} {escape(entry.name)}",
                    data={"type": "file", "path": entry_path, "index": n, "alpha": alpha},
                )
                self._fs_nodes[entry_path] = leaf

    def populate_tree(self) -> None:
        tree = self.app.query_one("#ast-tree", NavigableTree)
        tree.clear()
        self._fs_nodes.clear()
        base_dir = self._get_base_dir()

        # Mode A: Workspace Directory View (numbered 1, 2, 3 ...; first level of folders unfolded)
        if self.directory_mode:
            tree.root.label = f"📂 Workspace ({escape(base_dir.name)}/)"
            tree.root.data = {"type": "directory", "path": base_dir}
            tree.root.expand()
            self._populate_directory_node(tree.root, base_dir, [0], numeric=True, depth=0)
            self._restore_workspace_cursor()
            return

        # Mode B: Single-File AST Explorer
        root_block = self.editor.blocks[0] if self.editor.blocks else None
        fp = getattr(self.app, "filepath", None)
        root_name = root_block.name if root_block else (Path(fp).name if fp else "file.py")
        tree.root.label = f"📄 \\[0] Entire File ({escape(root_name)})"
        tree.root.data = 0
        tree.root.expand()

        cat_nodes: Dict[str, TreeNode] = {
            "filesystem": tree.root.add(f"📂 Directory Explorer ({escape(base_dir.name)}/)", expand=False),
            "imports": tree.root.add("📦 Imports", expand=False),
            "functions": tree.root.add("⚙️ Functions & Methods", expand=True),
            "statements": tree.root.add("📌 Statements & Expressions", expand=False),
            "variables": tree.root.add("💎 Variables", expand=False),
            "classes": tree.root.add("🧱 Classes", expand=True),
            "window": tree.root.add("🪟 Edit Windows", expand=True),
        }
        cat_nodes["filesystem"].data = {"type": "directory", "path": base_dir}
        self._populate_directory_node(cat_nodes["filesystem"], base_dir, [0])

        stage_nodes: Dict[int, TreeNode] = {
            n: tree.root.add(f"🏷️ Stage {n}", expand=True) for n in sorted(self.editor.stages.keys())
        }

        import_regex = re.compile(
            r"^\s*(import\s+|from\s+|\buse\b|\binclude\b|require\(|extern\s+crate)", re.IGNORECASE
        )
        class_regex = re.compile(
            r"^\s*(class\s+|struct\ |impl\ |trait\ |interface\ |type\ \w+\ =\ struct)", re.IGNORECASE
        )

        blocks_by_idx = {b.index: b for b in self.editor.blocks}
        for item in self.editor.get_summary().get("selection_array", []):
            idx = item["index"]
            if idx == 0:
                continue
            b_type = str(item.get("type", "")).lower()
            name = str(item.get("name", f"Block {idx}"))
            lines = item.get("lines", "")
            stage_id = item.get("stage")

            block_obj = blocks_by_idx.get(idx)
            raw_content = block_obj.content if block_obj else ""

            badge = (
                f"[bold #00d7ff]STAGE {stage_id}[/bold #00d7ff]"
                if stage_id is not None
                else "[dim #555555]\\[UNASSIGNED][/dim #555555]"
            )
            label = f"\\[{idx}] {escape(name)} ({lines}) {badge}"

            is_window = name.startswith("Window L")
            is_import = (
                any(k in b_type for k in ("import", "include", "use", "extern"))
                or bool(import_regex.search(name))
                or bool(import_regex.search(raw_content))
            )
            is_class = (
                any(k in b_type for k in ("class", "struct", "impl", "trait", "module"))
                or bool(class_regex.search(name))
                or bool(class_regex.search(raw_content))
            )

            if is_window:
                parent = cat_nodes["window"]
            elif stage_id is not None and stage_id in stage_nodes:
                parent = stage_nodes[stage_id]
            elif is_import:
                parent = cat_nodes["imports"]
            elif is_class:
                parent = cat_nodes["classes"]
            elif any(k in b_type for k in ("function", "method", "def", "func", "fn")):
                parent = cat_nodes["functions"]
            elif any(k in b_type for k in ("variable", "var", "const", "let")):
                parent = cat_nodes["variables"]
            else:
                parent = cat_nodes["statements"]

            parent.add_leaf(label, data=idx)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    def _open_file(self, target_path: Path) -> bool:
        try:
            resolved = target_path.resolve()
            new_editor = ModularBlockEditor(str(resolved))  # build first: a failure leaves state untouched
        except Exception as e:
            self.app.log_status(f"[bold #ff5f5f]Error opening {escape(target_path.name)}:[/bold #ff5f5f] {escape(str(e))}")
            return False

        pending = len(getattr(self.app.editor, "mutation_buffer", []) or [])
        if pending:
            self.app.log_status(f"[bold #ffb86c]Discarded {pending} unapplied mutation(s) from previous file.[/bold #ffb86c]")

        self.app.filepath = resolved
        self.app.editor = new_editor  # `self.editor` is a read-only property; set on the app
        self.app.language = self.app._detect_language()
        self.app.title = f"Modular Editor — {resolved.name}"

        if self.fs_root_path is None:
            self.fs_root_path = resolved.parent

        self.app.selected_block_id = None
        
        # Keep directory mode active if we were already browsing the workspace accordion view
        if not self.directory_mode:
            self.directory_mode = False

        history = getattr(self.app, "history_strategy", None)
        if history:
            history.attach()  # per-file undo tree; records out-of-band edits as a state

        self.populate_tree()
        self.app.log_status(f"[bold #00ffaf]Opened File:[/bold #00ffaf] {escape(resolved.name)}")
        return self.select_block(0)  # load the whole file into the active buffer

    def snapshot_selection(self) -> Optional[tuple]:
        """Identity of the selected block that survives a re-parse (indices shift, names mostly don't)."""
        sid = self.app.selected_block_id
        block = next((b for b in self.editor.blocks if b.index == sid), None) if sid is not None else None
        return None if block is None else (block.index, block.block_type, block.name, block.start_line)

    def restore_selection(self, snap: Optional[tuple]) -> bool:
        """Re-selects the block described by `snap` after the document was re-indexed."""
        if snap is None:
            return False
        idx, b_type, name, start = snap
        if idx == 0:
            return self.select_block(0)
        others = [b for b in self.editor.blocks if b.index != 0]
        same = [b for b in others if b.block_type == b_type and b.name == name]
        pool = same or [b for b in others if b.block_type == b_type]  # renamed: nearest of same kind
        if not pool:
            return self.select_block(0)
        return self.select_block(min(pool, key=lambda b: abs(b.start_line - start)).index)

    def select_block(self, target: Union[int, dict, str]) -> bool:
        """Handles selection of file/dir nodes (dict) and AST blocks (int / digit string)."""
        if isinstance(target, dict):
            node_type = target.get("type")
            target_path: Optional[Path] = target.get("path")
            if node_type == "file" and target_path and Path(target_path).is_file():
                return self._open_file(Path(target_path))
            if node_type == "directory":
                # Do NOT change fs_root_path here: it would desync the tree's [a]/[ab] labels.
                self.app.log_status(f"[#00d7ff]Selected Folder:[/#00d7ff] {escape(str(target_path))}")
                return True
            return False

        if isinstance(target, str):
            target = target.strip()
            if not target.isdigit():
                return self.jump_to_block(target)  # alphabetical file code
            target = int(target)

        if isinstance(target, int):
            block = next((b for b in self.editor.blocks if b.index == target), None)
            if block is None:
                self.app.log_status(f"[bold #ff5f5f]Error:[/bold #ff5f5f] Invalid block index [{target}].")
                return False
            language = getattr(self.app, "language", "python")
            if not getattr(self.app, "diff_mode", False):
                area = self.app.query_one("#content-input")
                if area.is_dirty and self.app.selected_block_id != block.index:
                    self.app.log_status("[#ffb86c]Discarded uncommitted edits in the buffer.[/#ffb86c]")
                area.load_block(
                    block.content,
                    language=language,
                    name=block.name,
                    start_line=block.start_line,
                    end_line=block.end_line,
                )
            self.app.selected_block_id = block.index
            self.app.log_status(
                f"[#00ffaf]Selected Block [{block.index}]:[/#00ffaf] {escape(block.name)} ({block.block_type})"
            )
            return True

        return False
