# modules/synths/src/editor/modular_editor.py
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Literal
import re
from pathlib import Path
import tree_sitter
from engine.analyzer import CodeAnalyzer, HAS_TREE_SITTER, LANGUAGES, Parser

@dataclass
class CodeBlock:
    index: int
    block_type: Literal["class", "function", "stage", "binding"]
    name: str
    start_line: int  # 1-indexed
    end_line: int    # 1-indexed
    stage_id: Optional[int] = None
    content: str = ""

@dataclass
class MutationOp:
    op_type: Literal["replace", "insert_before", "insert_after", "smart_replace"]
    target_indices: List[int]  # Supports batch targets like [1, 3, 4]
    new_content: str

### Core Modular Editor Engine

class ModularBlockEditor:
    """Edits modular code files via block indexing, AST parsing, and stage markers."""

    STAGE_REGEX = re.compile(r"^#\s*=+[\r\n]+#\s*Stage\s+(\d+)[\r\n]+#\s*=+", re.MULTILINE)

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.raw_code = self.filepath.read_text() if self.filepath.exists() else ""
        self.analyzer = CodeAnalyzer()
        self.blocks: List[CodeBlock] = []
        self.stages: Dict[int, Tuple[int, int]] = {}
        self.mutation_buffer: List[MutationOp] = []
        self.parse_document()

    def _get_ts_parser(self, ext: str) -> Optional[Parser]:
        """Helper to instantiate tree_sitter.Parser across API versions."""
        if not HAS_TREE_SITTER or ext not in LANGUAGES:
            return None
            
        lang_obj = LANGUAGES[ext]
        
        # 1. Convert raw pointer/capsule to tree_sitter.Language if necessary
        if not isinstance(lang_obj, tree_sitter.Language) and hasattr(tree_sitter, "Language"):
            try:
                lang_obj = tree_sitter.Language(lang_obj)
            except Exception:
                pass
    
        # 2. Instantiate parser using modern attribute setter, falling back to init args
        try:
            parser = Parser()
            parser.language = lang_obj
            return parser
        except (TypeError, AttributeError):
            try:
                return Parser(lang_obj)
            except Exception:
                return None

    def parse_document(self) -> None:
        """Parses the document into Stages and AST Blocks (Classes, Functions, Bindings)."""
        self.blocks.clear()
        self.stages.clear()
        lines = self.raw_code.splitlines()
        line_count = len(lines)

        # 1. Parse Stages
        stage_matches = list(self.STAGE_REGEX.finditer(self.raw_code))
        for i, match in enumerate(stage_matches):
            stage_num = int(match.group(1))
            start_line = self.raw_code[:match.start()].count('\n') + 1
            if i + 1 < len(stage_matches):
                end_line = self.raw_code[:stage_matches[i + 1].start()].count('\n')
            else:
                end_line = line_count
            self.stages[stage_num] = (start_line, end_line)
            
            # Add stage block
            self.blocks.append(CodeBlock(
                index=len(self.blocks),
                block_type="stage",
                name=f"Stage {stage_num}",
                start_line=start_line,
                end_line=end_line,
                stage_id=stage_num,
                content="\n".join(lines[start_line - 1:end_line])
            ))

        # 2. Extract Tree-Sitter / AST details with range boundaries
        ext = self.filepath.suffix.lower()
        parser = self._get_ts_parser(ext)
        
        if parser:
            tree = parser.parse(bytes(self.raw_code, "utf-8"))
            self._extract_ts_nodes(tree.root_node, lines)

        
    def _extract_ts_nodes(self, root_node, lines: List[str]) -> None:
        """Helper to walk tree-sitter AST nodes and create CodeBlocks."""
        func_types = {"function_definition", "async_function_definition", "binding"}
        class_types = {"class_definition", "struct_specifier"}

        def walk(node):
            if node.type in func_types or node.type in class_types:
                b_type = "class" if node.type in class_types else "function"
                name_node = node.child_by_field_name("name")
                name = name_node.text.decode("utf-8") if name_node else "unnamed"
                
                s_line = node.start_point[0] + 1
                e_line = node.end_point[0] + 1
                
                # Determine associated stage
                stage_id = None
                for sid, (s_start, s_end) in self.stages.items():
                    if s_start <= s_line <= s_end:
                        stage_id = sid
                        break

                self.blocks.append(CodeBlock(
                    index=len(self.blocks),
                    block_type=b_type,
                    name=name,
                    start_line=s_line,
                    end_line=e_line,
                    stage_id=stage_id,
                    content="\n".join(lines[s_line - 1:e_line])
                ))
            for child in node.children:
                walk(child)

        walk(root_node)

    # --- Inspection & Summaries ---

    def get_summary(self) -> Dict[str, Any]:
        """Provides file overview: class count, function count, stage count, and array overview."""
        funcs = [b for b in self.blocks if b.block_type == "function"]
        classes = [b for b in self.blocks if b.block_type == "class"]
        
        return {
            "file": str(self.filepath),
            "line_count": len(self.raw_code.splitlines()),
            "function_count": len(funcs),
            "class_count": len(classes),
            "stage_count": len(self.stages),
            "selection_array": [
                {
                    "index": b.index,
                    "type": b.block_type,
                    "name": b.name,
                    "stage": b.stage_id,
                    "lines": f"{b.start_line}-{b.end_line}"
                } for b in self.blocks
            ]
        }

    # --- Batch Operations & Queueing ---

    def queue_mutation(self, op_type: Literal["replace", "insert_before", "insert_after", "smart_replace"],
                       target_indices: List[int], content: str) -> None:
        """Buffers changes for grouped functions/blocks (e.g., [1, 3, 4])."""
        self.mutation_buffer.append(MutationOp(
            op_type=op_type,
            target_indices=target_indices,
            new_content=content
        ))

    def apply_batch(self) -> str:
        """Executes queued mutations in reverse line-order to prevent index shifting."""
        lines = self.raw_code.splitlines()

        # Gather target actions sorted by start_line descending
        actions = []
        for op in self.mutation_buffer:
            for idx in op.target_indices:
                block = next((b for b in self.blocks if b.index == idx), None)
                if block:
                    actions.append((block, op.op_type, op.new_content))

        # Sort descending by block start line
        actions.sort(key=lambda x: x[0].start_line, reverse=True)

        for block, op_type, new_text in actions:
            s_idx = block.start_line - 1
            e_idx = block.end_line

            if op_type == "replace":
                lines[s_idx:e_idx] = new_text.splitlines()
            elif op_type == "insert_before":
                lines[s_idx:s_idx] = new_text.splitlines()
            elif op_type == "insert_after":
                lines[e_idx:e_idx] = new_text.splitlines()
            elif op_type == "smart_replace":
                # Smart replace: updates block while keeping indentation and signature structure
                orig_indent = len(lines[s_idx]) - len(lines[s_idx].lstrip())
                indented = [" " * orig_indent + l if l.strip() else l for l in new_text.splitlines()]
                lines[s_idx:e_idx] = indented

        self.raw_code = "\n".join(lines)
        self.mutation_buffer.clear()
        self.parse_document()  # Re-index tree
        return self.raw_code
