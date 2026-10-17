"""Navigation strategy for single-file AST semantic breakdown and workspace directory exploration."""
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Union
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


class DefaultNavigationStrategy(NavigationStrategy):
    """Navigation strategy supporting single-file AST semantic views and 
    workspace directory filesystem exploration with document numbering and full file preview reload.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.directory_mode: bool = False
        self.fs_root_path: Optional[Path] = None

    def set_filesystem_mode(self, directory_mode: bool, root_path: Optional[Path] = None) -> None:
        """Toggles between Directory Explorer mode and single-file AST view."""
        self.directory_mode = directory_mode
        if root_path is not None:
            self.fs_root_path = root_path.resolve()
        elif hasattr(self.app, "filepath") and self.app.filepath:
            self.fs_root_path = self.app.filepath.parent.resolve()
                
        self.populate_tree()

    def resolve_anchor(self, line_num: int) -> Optional[int]:
        if hasattr(self.editor, "create_line_window_block"):
            block_idx = self.editor.create_line_window_block(line_num, radius=3)
            if block_idx is not None:
                self.populate_tree()
                return block_idx

        matching = [
            b
            for b in self.editor.blocks
            if b.index != 0
            and getattr(b, "start_line", 0) <= line_num <= getattr(b, "end_line", 0)
        ]
        if matching:
            best = min(matching, key=lambda b: b.end_line - b.start_line)
            return best.index
        return None

    def _populate_directory_node(self, parent_node: TreeNode, dir_path: Path) -> None:
        """Recursively populates file tree nodes starting from dir_path with numbered documents."""
        try:
            entries = sorted(
                os.scandir(dir_path),
                key=lambda e: (not e.is_dir(), e.name.lower()),
            )
        except PermissionError:
            return

        file_index = 0
        for entry in entries:
            if entry.name.startswith(".") or entry.name in (
                "__pycache__",
                "node_modules",
                "target",
                "result",
                ".git",
            ):
                continue

            entry_path = Path(entry.path)
            if entry.is_dir():
                dir_node = parent_node.add(f"📁 {entry.name}", expand=False)
                dir_node.data = {"type": "directory", "path": entry_path}
                self._populate_directory_node(dir_node, entry_path)
            else:
                file_index += 1
                is_active = (
                    hasattr(self.app, "filepath")
                    and self.app.filepath
                    and entry_path.resolve() == self.app.filepath.resolve()
                )
                icon = "🎯" if is_active else "📄"
                parent_node.add_leaf(
                    f"{file_index}. {icon} {entry.name}",
                    data={"type": "file", "path": entry_path},
                )

    def populate_tree(self) -> None:
        """Populates the tree view according to the active mode (Directory vs AST)."""
        tree = self.app.query_one("#ast-tree", NavigableTree)
        tree.clear()

        base_dir = (
            self.fs_root_path
            if self.fs_root_path
            else self.app.filepath.parent.resolve()
        )

        # Mode A: Workspace Directory View
        if self.directory_mode:
            tree.root.label = f"📂 Workspace ({base_dir.name}/)"
            tree.root.data = {"type": "directory", "path": base_dir}
            tree.root.expand()
            self._populate_directory_node(tree.root, base_dir)
            return

        # Mode B: Single-File AST Explorer
        root_block = self.editor.blocks[0] if self.editor.blocks else None
        root_name = root_block.name if root_block else self.app.filepath.name
        tree.root.label = f"📄 [0] Entire File ({root_name})"
        tree.root.data = 0
        tree.root.expand()

        cat_nodes: Dict[str, TreeNode] = {
            "filesystem": tree.root.add(f"📂 Directory Explorer ({base_dir.name}/)", expand=False),
            "imports": tree.root.add("📦 Imports", expand=False),
            "functions": tree.root.add("⚙️ Functions & Methods", expand=True),
            "statements": tree.root.add("📌 Statements & Expressions", expand=False),
            "variables": tree.root.add("💎 Variables", expand=False),
            "classes": tree.root.add("🧱 Classes", expand=True),
            "window": tree.root.add("🪟 Edit Windows", expand=True),
        }
        cat_nodes["filesystem"].data = {"type": "directory", "path": base_dir}
        self._populate_directory_node(cat_nodes["filesystem"], base_dir)

        stage_nodes: Dict[int, TreeNode] = {}
        if hasattr(self.editor, "stages"):
            for stage_num in sorted(self.editor.stages.keys()):
                stage_nodes[stage_num] = tree.root.add(
                    f"🏷️ Stage {stage_num}", expand=True
                )

        import_regex = re.compile(
            r"^\s*(import\s+|from\s+|\buse\b|\binclude\b|require\(|extern\s+crate)",
            re.IGNORECASE,
        )
        class_regex = re.compile(
            r"^\s*(class\s+|struct\ |impl\ |trait\ |interface\ |type\ \w+\ =\ struct)",
            re.IGNORECASE,
        )

        summary = self.editor.get_summary()
        for item in summary.get("selection_array", []):
            idx = item["index"]
            if idx == 0:
                continue
            b_type = str(item.get("type", "")).lower()
            name = str(item.get("name", f"Block {idx}"))
            lines = item.get("lines", "")
            stage_id = item.get("stage")

            block_obj = next((b for b in self.editor.blocks if b.index == idx), None)
            raw_content = block_obj.content if block_obj else ""

            badge = (
                f"[bold #00d7ff]STAGE {stage_id}[/bold #00d7ff]"
                if stage_id is not None
                else "[dim #555555][UNASSIGNED][/dim #555555]"
            )
            label = f"[{idx}] {name} ({lines}) {badge}"

            is_import = (
                any(k in b_type for k in ["import", "include", "use", "extern"])
                or import_regex.search(name)
                or import_regex.search(raw_content)
            )
            is_class = (
                any(
                    k in b_type
                    for k in ["class", "struct", "impl", "trait", "module"]
                )
                or class_regex.search(name)
                or class_regex.search(raw_content)
            )

            if stage_id is not None and stage_id in stage_nodes:
                parent = stage_nodes[stage_id]
            elif is_import:
                parent = cat_nodes["imports"]
            elif is_class:
                parent = cat_nodes["classes"]
            elif any(k in b_type for k in ["function", "method", "def", "func", "fn"]):
                parent = cat_nodes["functions"]
            elif any(k in b_type for k in ["variable", "var", "const", "let"]):
                parent = cat_nodes["variables"]
            elif any(k in b_type for k in ["window", "edit_window", "range"]):
                parent = cat_nodes["window"]
            else:
                parent = cat_nodes["statements"]

            parent.add_leaf(label, data=idx)

    def select_block(self, target: Union[int, dict]) -> bool:
        """Handles selection events for both polymorphic filesystem node dicts and integer AST blocks."""
        # 1. Handle Filesystem Tree Selection (dict payload)
        if isinstance(target, dict):
            node_type = target.get("type")
            target_path: Optional[Path] = target.get("path")
            if node_type == "file" and target_path and target_path.is_file():
                try:
                    resolved_path = target_path.resolve()
                    self.app.filepath = resolved_path
                    self.app.editor = ModularBlockEditor(str(resolved_path))
                    self.app.language = self.app._detect_language()
                    self.app.title = f"Modular Editor — {resolved_path.name}"
                    
                    # Update root context path to the new file's parent directory
                    self.fs_root_path = resolved_path.parent.resolve()
                    self.app.selected_block_id = 0
                    self.directory_mode = False
                    self.populate_tree()

                    # Reload the preview pane and text input with the entire file content (Block 0)
                    if self.editor.blocks:
                        root_block = self.editor.blocks[0]
                        if not getattr(self.app, "diff_mode", False):
                            preview = self.app.query_one("#preview-pane")
                            preview.update_view(
                                root_block.content,
                                language=getattr(self.app, "language", "python"),
                                line_start=getattr(root_block, "start_line", 1),
                            )
                            text_area = self.app.query_one("#content-input")
                            text_area.text = root_block.content

                        target_preview = self.app.query_one("#target-preview")
                        target_preview.update_target(
                            root_block, language=getattr(self.app, "language", "python")
                        )

                    self.app.log_status(
                        f"[bold #00ffaf]Opened File & Loaded Entire Code:[/bold #00ffaf] {resolved_path.name}"
                    )
                    return True
                except Exception as e:
                    self.app.log_status(
                        f"[bold #ff5f5f]Error opening file {target_path.name}:[/bold #ff5f5f] {e}"
                    )
                    return False
            elif node_type == "directory":
                self.fs_root_path = target_path.resolve() if target_path else self.fs_root_path
                self.app.log_status(
                    f"[#00d7ff]Selected Folder:[/#00d7ff] {target_path}"
                )
                return True
            return False

        # 2. Handle AST Block Selection (int index)
        if isinstance(target, int):
            block_idx = target
            block = next((b for b in self.editor.blocks if b.index == block_idx), None)
            if block:
                self.app.selected_block_id = block_idx
                if not getattr(self.app, "diff_mode", False):
                    preview = self.app.query_one("#preview-pane")
                    preview.update_view(
                        block.content,
                        language=getattr(self.app, "language", "python"),
                        line_start=getattr(block, "start_line", 1),
                    )
                    text_area = self.app.query_one("#content-input")
                    text_area.text = block.content

                target_preview = self.app.query_one("#target-preview")
                target_preview.update_target(
                    block, language=getattr(self.app, "language", "python")
                )
                self.app.log_status(
                    f"[#00ffaf]Selected Block [{block.index}]:[/#00ffaf] {block.name} ({block.block_type})"
                )
                return True

            self.app.log_status(
                f"[bold #ff5f5f]Error:[/bold #ff5f5f] Invalid block index [{target}]."
            )
            return False

        return False
