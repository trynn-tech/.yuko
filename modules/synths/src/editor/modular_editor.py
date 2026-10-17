# modules/synth/src/editor/modular_editor.py
import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import tree_sitter
from engine.analyzer import HAS_TREE_SITTER, LANGUAGES, CodeAnalyzer, Parser


@dataclass
class CodeBlock:
    index: int
    block_type: Literal[
        "class",
        "function",
        "stage",
        "binding",
        "variable",
        "statement",
        "file_root",
    ]
    name: str
    start_line: int  # 1-indexed
    end_line: int  # 1-indexed
    stage_id: Optional[int] = None
    content: str = ""


@dataclass
class MutationOp:
    op_type: Literal["replace", "insert_before", "insert_after", "smart_replace"]
    target_indices: List[int]
    new_content: str


class ModularBlockEditor:
    """Edits modular code files via block indexing, AST parsing, and stage markers."""

    STAGE_REGEX = re.compile(
        r"^#\s*=+[\r\n]+#\s*Stage\s+(\d+)[\r\n]+#\s*=+", re.MULTILINE
    )

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.raw_code = self.filepath.read_text() if self.filepath.exists() else ""
        self.original_code = self.raw_code
        self.analyzer = CodeAnalyzer()
        self.blocks: List[CodeBlock] = []
        self.stages: Dict[int, Tuple[int, int]] = {}
        self.mutation_buffer: List[MutationOp] = []
        self.parse_document()

    def _get_ts_parser(self, ext: str) -> Optional[Any]:
        if not HAS_TREE_SITTER or ext not in LANGUAGES:
            return None
        lang_obj = LANGUAGES[ext]

        # Handle API variation across tree-sitter bindings
        try:
            if hasattr(tree_sitter, "Language") and not isinstance(
                lang_obj, tree_sitter.Language
            ):
                lang_obj = tree_sitter.Language(lang_obj)
        except Exception:
            pass

        try:
            # Modern bindings (tree-sitter >= 0.22.0)
            p = Parser(lang_obj)
            return p
        except (TypeError, AttributeError):
            try:
                # Legacy bindings (tree-sitter <= 0.21.0)
                p = Parser()
                p.set_language(lang_obj)
                return p
            except Exception:
                return None

    def parse_document(self) -> None:
        """Parses document into Stages, Full Document Root [0], and complete AST Nodes."""
        self.blocks.clear()
        self.stages.clear()
        lines = self.raw_code.splitlines()
        line_count = len(lines)

        # Index [0]: Full Document Root Block
        self.blocks.append(
            CodeBlock(
                index=0,
                block_type="file_root",
                name=self.filepath.name,
                start_line=1,
                end_line=max(1, line_count),
                stage_id=None,
                content=self.raw_code,
            )
        )

        # 1. Parse Stages
        stage_matches = list(self.STAGE_REGEX.finditer(self.raw_code))
        for i, match in enumerate(stage_matches):
            stage_num = int(match.group(1))
            start_line = self.raw_code[: match.start()].count("\n") + 1
            end_line = (
                self.raw_code[: stage_matches[i + 1].start()].count("\n")
                if i + 1 < len(stage_matches)
                else line_count
            )
            self.stages[stage_num] = (start_line, end_line)

            self.blocks.append(
                CodeBlock(
                    index=len(self.blocks),
                    block_type="stage",
                    name=f"Stage {stage_num}",
                    start_line=start_line,
                    end_line=end_line,
                    stage_id=stage_num,
                    content="\n".join(lines[start_line - 1 : end_line]),
                )
            )

        # 2. Complete AST Extraction
        ext = self.filepath.suffix.lower()
        parser = self._get_ts_parser(ext)
        if parser:
            tree = parser.parse(bytes(self.raw_code, "utf-8"))
            self._extract_ts_nodes(tree.root_node, lines)

    def _extract_ts_nodes(self, root_node, lines: List[str]) -> None:
        """Traverses AST capturing top-level structures and preventing over-nested duplicates."""
        func_types = {"function_definition", "async_function_definition", "binding"}
        class_types = {"class_definition", "struct_specifier"}
        var_types = {"assignment", "variable_declarator"}
        stmt_types = {
            "expression_statement",
            "import_statement",
            "import_from_statement",
        }

        def walk(node):
            node_type = node.type
            matched = False

            if node_type in class_types or node_type in func_types:
                matched = True
                b_type = "class" if node_type in class_types else "function"
                name_node = node.child_by_field_name("name")
                name = (
                    name_node.text.decode("utf-8").strip()
                    if name_node
                    else "unnamed"
                )

            elif node_type in var_types:
                matched = True
                b_type = "variable"
                name_node = node.child_by_field_name(
                    "name"
                ) or node.child_by_field_name("left")
                name = (
                    name_node.text.decode("utf-8").strip()
                    if name_node
                    else "var"
                )

            elif node_type in stmt_types:
                # Avoid capturing statement wrappers around already matched variables
                if not any(child.type in var_types for child in node.children):
                    matched = True
                    b_type = "statement"
                    raw_text = (
                        node.text.decode("utf-8").splitlines()[0]
                        if node.text
                        else "expr"
                    )
                    name = (
                        (raw_text[:25] + "...")
                        if len(raw_text) > 25
                        else raw_text
                    )

            if matched:
                s_line = node.start_point[0] + 1
                e_line = node.end_point[0] + 1

                stage_id = None
                for sid, (s_start, s_end) in self.stages.items():
                    if s_start <= s_line <= s_end:
                        stage_id = sid
                        break

                self.blocks.append(
                    CodeBlock(
                        index=len(self.blocks),
                        block_type=b_type,
                        name=name,
                        start_line=s_line,
                        end_line=e_line,
                        stage_id=stage_id,
                        content="\n".join(lines[s_line - 1 : e_line]),
                    )
                )

            # Traverse child nodes
            for child in node.children:
                walk(child)

        walk(root_node)

    def get_summary(self) -> Dict[str, Any]:
        return {
            "file": str(self.filepath),
            "line_count": len(self.raw_code.splitlines()),
            "function_count": len(
                [b for b in self.blocks if b.block_type == "function"]
            ),
            "class_count": len(
                [b for b in self.blocks if b.block_type == "class"]
            ),
            "variable_count": len(
                [b for b in self.blocks if b.block_type == "variable"]
            ),
            "stage_count": len(self.stages),
            "selection_array": [
                {
                    "index": b.index,
                    "type": b.block_type,
                    "name": b.name,
                    "stage": b.stage_id,
                    "lines": f"{b.start_line}-{b.end_line}",
                }
                for b in self.blocks
            ],
        }

    def generate_diff(self) -> str:
        """Returns a unified diff string between disk state and modified state."""
        orig = self.original_code.splitlines(keepends=True)
        curr = self.raw_code.splitlines(keepends=True)
        diff = difflib.unified_diff(
            orig,
            curr,
            fromfile=f"a/{self.filepath.name}",
            tofile=f"b/{self.filepath.name}",
        )
        return "".join(diff)

    def queue_mutation(
        self,
        op_type: Literal[
            "replace", "insert_before", "insert_after", "smart_replace"
        ],
        target_indices: List[int],
        content: str,
    ) -> None:
        self.mutation_buffer.append(
            MutationOp(
                op_type=op_type,
                target_indices=target_indices,
                new_content=content,
            )
        )

    def apply_batch(self) -> str:
        lines = self.raw_code.splitlines()
        actions = []

        for op in self.mutation_buffer:
            for idx in op.target_indices:
                block = next((b for b in self.blocks if b.index == idx), None)
                if block:
                    actions.append((block, op.op_type, op.new_content))

        # Check for full file replacement first
        root_action = next((a for a in actions if a[0].index == 0), None)
        if root_action:
            self.raw_code = root_action[2]
            self.mutation_buffer.clear()
            self.parse_document()
            return self.raw_code

        # Re-apply in descending line order to avoid offset collisions
        actions.sort(key=lambda x: x[0].start_line, reverse=True)

        for block, op_type, new_text in actions:
            s_idx = block.start_line - 1
            e_idx = block.end_line
            new_lines = new_text.splitlines()

            if op_type == "replace":
                lines[s_idx:e_idx] = new_lines
            elif op_type == "insert_before":
                lines[s_idx:s_idx] = new_lines
            elif op_type == "insert_after":
                lines[e_idx:e_idx] = new_lines
            elif op_type == "smart_replace":
                orig_indent = (
                    len(lines[s_idx]) - len(lines[s_idx].lstrip())
                    if s_idx < len(lines)
                    else 0
                )
                indented = [
                    " " * orig_indent + l if l.strip() else l for l in new_lines
                ]
                lines[s_idx:e_idx] = indented

        self.raw_code = "\n".join(lines)
        self.mutation_buffer.clear()
        self.parse_document()
        return self.raw_code

    def create_line_window_block(
        self, anchor_line: int, radius: int = 3
    ) -> CodeBlock:
        """Generates a dynamic CodeBlock centered around an anchor line (anchor ± radius)."""
        lines = self.raw_code.splitlines()
        total_lines = len(lines)

        start_line = max(1, anchor_line - radius)
        end_line = min(total_lines, anchor_line + radius)

        content = "\n".join(lines[start_line - 1 : end_line])

        block = CodeBlock(
            index=len(self.blocks),
            block_type="statement",
            name=f"Window L{anchor_line} (±{radius})",
            start_line=start_line,
            end_line=end_line,
            stage_id=None,
            content=content,
        )

        self.blocks.append(block)
        return block
