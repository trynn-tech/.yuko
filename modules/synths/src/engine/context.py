#!/usr/bin/env python3
# modules/synths/src/engine/context.py

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
from pydantic import BaseModel


class FileContext(BaseModel):
    path: Path
    relative_path: str
    content: str = ""
    exists: bool = True
    windows: List[Dict[str, Any]] = []


class RepoContext:
    """Discovers repository structure and builds prompts using ripgrep & fd,
    supporting sliding window context slicing and directional vector/symbolic metadata.
    """

    def __init__(
        self,
        root_path: Optional[Path] = None,
        max_file_lines: int = 400,
        embedder: Optional[Any] = None,
        graph_linker: Optional[Any] = None,
    ):
        self.root_path = (root_path or Path.cwd()).resolve()
        self.has_rg = shutil.which("rg") is not None
        self.has_fd = shutil.which("fd") is not None
        self.max_file_lines = max_file_lines
        self.embedder = embedder
        self.graph_linker = graph_linker

    def build_directional_metadata(self, instruction: str, filepath: str) -> str:
        """Builds a low-overhead directional metadata block using vector embeddings and graph facts."""
        metadata_parts = []

        # 1. Symbolic Direction (Neo4j Graph Facts)
        if self.graph_linker:
            try:
                graph_ctx = self.graph_linker.retrieve_graph_context(
                    keywords=[Path(filepath).stem], limit=5
                )
                if graph_ctx:
                    metadata_parts.append(f"<symbolic_context>\n{graph_ctx}\n</symbolic_context>")
            except Exception:
                pass

        # 2. Semantic Direction (Vector Embeddings via TextEmbedder)
        if self.embedder and hasattr(self.embedder, "search_similar"):
            try:
                similar_snippets = self.embedder.search_similar(instruction, top_k=2)
                if similar_snippets:
                    snippets_str = "\n".join(
                        [f"- {s.get('path')}: {s.get('summary')}" for s in similar_snippets]
                    )
                    metadata_parts.append(f"<semantic_references>\n{snippets_str}\n</semantic_references>")
            except Exception:
                pass

        return "\n\n".join(metadata_parts)

    def collect_context(self, filepath: str, target_symbol: str = "", instruction: str = "") -> str:
        """Gathers context for a target file path, injecting directional metadata and sliding windows."""
        target_path = Path(filepath)
        contexts = self.build_context([target_path], target_symbol=target_symbol)
        formatted_blocks = []

        # Prepend low-overhead directional map if instruction is provided
        if instruction:
            directional_meta = self.build_directional_metadata(instruction, filepath)
            if directional_meta:
                formatted_blocks.append(directional_meta)

        for ctx in contexts:
            if not ctx.exists:
                continue
            if ctx.windows:
                for w in ctx.windows:
                    formatted_blocks.append(
                        f"### File: {ctx.relative_path} (Lines {w['start_line']}-{w['end_line']})\n```\n{w['content']}\n```"
                    )
            elif ctx.content:
                formatted_blocks.append(
                    f"### File: {ctx.relative_path}\n```\n{ctx.content}\n```"
                )

        return "\n\n".join(formatted_blocks)

    def get_sliding_window_context(
        self, content: str, target_symbol: str = "", window_lines: int = 250, overlap: int = 50
    ) -> List[Dict[str, Any]]:
        """Splits large source files into overlapping sliding windows prioritized by symbol relevance."""
        lines = content.splitlines()
        total_lines = len(lines)

        if total_lines <= window_lines:
            return [{"start_line": 1, "end_line": total_lines, "content": content, "relevance": 1.0}]

        chunks = []
        step = window_lines - overlap
        for start in range(0, total_lines, step):
            end = min(start + window_lines, total_lines)
            chunk_content = "\n".join(lines[start:end])

            contains_symbol = target_symbol in chunk_content if target_symbol else True
            relevance = 1.0 if contains_symbol else 0.5

            chunks.append({
                "start_line": start + 1,
                "end_line": end,
                "content": chunk_content,
                "relevance": relevance,
            })

            if end == total_lines:
                break

        return sorted(chunks, key=lambda x: x["relevance"], reverse=True)

    def resolve_path_recursively(self, target: str) -> Optional[Path]:
        candidate = Path(target)
        direct_path = candidate if candidate.is_absolute() else (self.root_path / target).resolve()
        if direct_path.exists():
            return direct_path
        if self.has_fd:
            filename = candidate.name
            try:
                cmd = ["fd", "-H", "-I", "--type", "f", f"^{filename}$", str(self.root_path)]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                matches = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                if matches:
                    return Path(matches[0]).resolve()
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        return None

    def find_file_by_anchor(self, search_anchor: str) -> Optional[Path]:
        if not self.has_rg or not search_anchor.strip():
            return None
        lines = [l.strip() for l in search_anchor.splitlines() if l.strip()]
        if not lines:
            return None
        query = lines[0]
        try:
            cmd = ["rg", "--fixed-strings", "--files-with-matches", query, str(self.root_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            matches = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            if matches:
                return Path(matches[0]).resolve()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    def build_context(self, target_paths: List[Path], target_symbol: str = "") -> List[FileContext]:
        contexts: List[FileContext] = []
        for raw_path in target_paths:
            resolved = self.resolve_path_recursively(str(raw_path))
            target = resolved or (self.root_path / raw_path).resolve()
            if target.exists():
                if target.is_file():
                    try:
                        content = target.read_text(encoding="utf-8")
                        rel_path = self._to_rel_path(target)

                        windows = []
                        if len(content.splitlines()) > self.max_file_lines:
                            windows = self.get_sliding_window_context(content, target_symbol=target_symbol)

                        contexts.append(
                            FileContext(
                                path=target,
                                relative_path=rel_path,
                                content=content if not windows else "",
                                exists=True,
                                windows=windows,
                            )
                        )
                    except Exception:
                        contexts.append(FileContext(path=target, relative_path=str(target), content="", exists=True))
                elif target.is_dir() and self.has_fd:
                    try:
                        cmd = ["fd", "--type", "f", "--max-depth", "3", str(target)]
                        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                        discovered = [Path(p) for p in result.stdout.splitlines() if p.strip()]
                        for sub_path in discovered[:10]:
                            try:
                                content = sub_path.read_text(encoding="utf-8")
                                rel_path = self._to_rel_path(sub_path)
                                contexts.append(
                                    FileContext(path=sub_path, relative_path=rel_path, content=content, exists=True)
                                )
                            except Exception:
                                pass
                    except subprocess.CalledProcessError:
                        pass
            else:
                rel_path = self._to_rel_path(target)
                contexts.append(FileContext(path=target, relative_path=rel_path, content="", exists=False))
        return contexts

    def _to_rel_path(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root_path))
        except ValueError:
            return str(path)
