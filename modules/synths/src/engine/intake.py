#!/usr/bin/env python3
# modules/synths/src/engine/intake.py

import ast
import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from rich.console import Console

console = Console()
logger = logging.getLogger(__name__)

SCRIPT_DELIMITER = "=^-.-^="

LANG_DISPATCH = {
    ".py": {
        "file_cmd": lambda f: [sys.executable, f],
        "eval_cmd": lambda c: [sys.executable, "-c", c],
    },
    ".nix": {
        "file_cmd": lambda f: ["nix-instantiate", "--eval", "--strict", f],
        "eval_cmd": lambda c: ["nix-instantiate", "--eval", "--expr", c],
    },
    ".sh": {
        "file_cmd": lambda f: ["bash", f],
        "eval_cmd": lambda c: ["bash", "-c", c],
    },
    ".bash": {
        "file_cmd": lambda f: ["bash", f],
        "eval_cmd": lambda c: ["bash", "-c", c],
    },
    ".zsh": {
        "file_cmd": lambda f: ["zsh", f],
        "eval_cmd": lambda c: ["zsh", "-c", c],
    },
}


class ScriptIntakeResult:
    """Holds the result of a script intake execution pass."""

    def __init__(
        self,
        success: bool,
        returncode: int,
        stdout: str,
        stderr: str,
        modified_files: List[str],
        ephemeral_driver_used: bool = False,
    ):
        self.success = success
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.modified_files = modified_files
        self.ephemeral_driver_used = ephemeral_driver_used

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "modified_files": self.modified_files,
            "ephemeral_driver_used": self.ephemeral_driver_used,
        }


class ScriptStreamHandler:
    """Dynamic builder and orchestrator for LLM-driven workspace mutations.
    Supports ephemeral python editor drivers, resilient patch blocks, and contextual driver fallbacks.
    """

    def __init__(self, executor: Any, repo_path: Optional[Path] = None):
        self.executor = executor
        self.repo_path = (repo_path or Path.cwd()).resolve()


    def process_stream(self, raw_stream_content: str) -> ScriptIntakeResult:
        """Processes LLM stream output into declarative file edits, ephemeral python operations,
        or driver executions.
        """
        clean_content = self.strip_delimiters(raw_stream_content)
        modified_files: List[str] = []

        # 1. Process declarative filesystem directives (CREATE / EDIT / DELETE)
        created_files = self._parse_and_apply_declarative_ops(clean_content)
        if created_files:
            modified_files.extend(created_files)
            primary_target = self._select_primary_target(modified_files)
            if primary_target and Path(primary_target).exists():
                return self.run_target_file(
                    primary_target, modified_files=modified_files
                )
            return ScriptIntakeResult(
                success=True,
                returncode=0,
                stdout="Declarative operations applied.",
                stderr="",
                modified_files=modified_files,
            )

        # 2. Extract explicit code block and targets
        runnable_code, target_file = self._extract_runnable_target(clean_content)

        # CASE A: Self-destructing/ephemeral Python driver script
        if runnable_code and self._is_ephemeral_driver(target_file, runnable_code):
            driver_path = target_file or "_ephemeral_driver.py"
            return self._execute_ephemeral_driver(
                driver_path, runnable_code, modified_files
            )

        # 3. Apply standard search/replace patches if present
        blocks = self.executor.patcher.parse_blocks(
            clean_content, fallback_filepath=None
        )
        if blocks:
            for block in blocks:
                target_path = self._resolve_target_file_path(block.filepath)
                if not target_path:
                    continue
                target_str = str(target_path)
                if block.search_anchor:
                    if self.executor.apply_resilient_edit(
                        target_str, block.search_anchor, block.replace_block
                    ):
                        if target_str not in modified_files:
                            modified_files.append(target_str)
                else:
                    if self.executor.write_file(target_str, block.replace_block):
                        if target_str not in modified_files:
                            modified_files.append(target_str)

        # CASE B: Standard code targeted at a specific workspace file
        if target_file and runnable_code:
            target_path = self._resolve_target_file_path(target_file)
            if target_path:
                target_str = str(target_path)
                self.executor.write_file(target_str, runnable_code)
                if target_str not in modified_files:
                    modified_files.append(target_str)
                return self.run_target_file(target_str, modified_files=modified_files)

        # CASE C: Default back to executing a contextual entry point (or modified file)
        primary_target = self._select_primary_target(modified_files)
        if primary_target and Path(primary_target).exists():
            return self.run_target_file(
                primary_target, modified_files=modified_files
            )

        # CASE D: Fall back to inline raw evaluation (e.g. string/expression execution)
        sanitized_code = re.sub(
            r"^\s*(?:CREATE|DELETE)\s+.*$", "", clean_content, flags=re.MULTILINE
        ).strip()
        sanitized_code = self._strip_code_fences(sanitized_code)
        if "<<<<<<< SEARCH" in sanitized_code:
            return ScriptIntakeResult(
                success=False,
                returncode=1,
                stdout="",
                stderr="Resilient patch anchors failed to match target file.",
                modified_files=modified_files,
            )
        lang_ext = self._detect_stream_language(clean_content)
        return self.run_raw_string(
            sanitized_code, lang_ext=lang_ext, modified_files=modified_files
        )

    def _extract_runnable_target(
        self, script_text: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extracts code block body and target path from headers or inline annotations."""
        match = re.search(
            r"```(?:[a-zA-Z0-9_-]+)?[\n\r]+(.*?)(?:\n```|$)",
            script_text,
            re.DOTALL | re.IGNORECASE,
        )
        if match:
            code = match.group(1).strip()
            target_match = re.search(r"#\s*target:\s*([^\n#]+)", code)
            if target_match:
                target_file = target_match.group(1).strip()
                target_file = re.sub(r"\s*\(.*?\)$", "", target_file).strip()
            else:
                target_file = None
            return code, target_file
        return None, None

    def _is_ephemeral_driver(self, target_file: Optional[str], code_body: str) -> bool:
        """Determines if code block is an ephemeral script via header flags, naming, or AST heuristics."""
        # 1. Direct header annotation checks
        if re.search(r"#\s*ephemeral:\s*true", code_body, re.IGNORECASE):
            return True
        if target_file and re.search(r"(?:ephemeral|temp|_driver)", target_file, re.IGNORECASE):
            return True

        # 2. AST Heuristic: Heavy import of IO/AST tools + top-level mutation statements
        try:
            tree = ast.parse(code_body)
        except SyntaxError:
            return False

        manipulator_modules = {"ast", "pathlib", "shutil", "os", "re", "sys", "glob"}
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_names.add(node.module.split('.')[0])

        has_manipulators = bool(imported_names.intersection(manipulator_modules))
        has_top_level_actions = any(
            isinstance(stmt, (ast.Expr, ast.Assign, ast.For, ast.With))
            for stmt in tree.body
        )
        return has_manipulators and has_top_level_actions


    def _resolve_target_file_path(self, raw_filepath: str) -> Optional[Path]:
        """Resolves target paths, finding existing entry points if a directory is specified."""
        if not raw_filepath or not raw_filepath.strip():
            return None
        clean_path = Path(raw_filepath.strip())
        target = self.repo_path / clean_path if not clean_path.is_absolute() else clean_path
        if target.is_dir() or raw_filepath.endswith("/"):
            candidates = ["main.py", "__main__.py", "driver.py", "default.nix", "flake.nix"]
            for candidate in candidates:
                check = target / candidate
                if check.exists():
                    return check
            return target / "main.py"
        return target


    def _execute_ephemeral_driver(
        self, target_file: str, code: str, modified_files: List[str]
    ) -> ScriptIntakeResult:
        """Writes an ephemeral python script, executes it to perform dynamic directory/file IO,
        and ensures the driver self-destructs afterwards.
        """
        temp_path = self.repo_path / target_file
        try:
            self.executor.write_file(str(temp_path), code)
            result = self.run_target_file(str(temp_path), modified_files=modified_files)
            result.ephemeral_driver_used = True
            return result
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except OSError as e:
                    logger.warning(f"Failed to cleanup ephemeral driver {temp_path}: {e}")

    def strip_delimiters(self, text: str) -> str:
        """Strips leading and trailing intake delimiters."""
        cleaned = text.strip()
        if cleaned.startswith(SCRIPT_DELIMITER):
            cleaned = cleaned[len(SCRIPT_DELIMITER) :].lstrip()
        if cleaned.endswith(SCRIPT_DELIMITER):
            cleaned = cleaned[: -len(SCRIPT_DELIMITER)].rstrip()
        return cleaned

    def _select_primary_target(self, modified_files: List[str]) -> Optional[str]:
        """Resolves target driver from modified files, existing entrypoints, or first modified target."""
        if not modified_files:
            root_main = self.repo_path / "main.py"
            return str(root_main) if root_main.exists() else None
        for file_path in modified_files:
            if Path(file_path).name in ("main.py", "__main__.py", "driver.py"):
                return file_path
        for file_path in modified_files:
            if file_path.endswith((".py", ".nix", ".sh")):
                return file_path
        return modified_files[0]

    def _detect_stream_language(self, content: str) -> str:
        match = re.search(r"```([a-zA-Z0-9_-]+)", content)
        if match:
            lang = match.group(1).lower()
            mapping = {
                "python": ".py",
                "py": ".py",
                "nix": ".nix",
                "sh": ".sh",
                "bash": ".sh",
                "zsh": ".zsh",
            }
            return mapping.get(lang, ".py")
        return ".py"

    def _strip_code_fences(self, text: str) -> str:
        lines = text.strip().splitlines()
        if lines and re.match(r"^\s*```[a-zA-Z0-9_-]*\s*$", lines[0]):
            lines = lines[1:]
        if lines and re.match(r"^\s*```\s*$", lines[-1]):
            lines = lines[:-1]
        return "\n".join(lines).strip()


    def _parse_and_apply_declarative_ops(self, script_text: str) -> List[str]:
        modified = []

        # Process DELETE directives
        for match in re.finditer(r"^\s*DELETE\s+(.+)$", script_text, re.MULTILINE):
            rel_path = match.group(1).strip()
            target_path = self.repo_path / rel_path if not Path(rel_path).is_absolute() else Path(rel_path)
            if target_path.exists():
                try:
                    target_path.unlink()
                    modified.append(str(target_path))
                except OSError as e:
                    logger.warning(f"Failed to delete {target_path}: {e}")

        # Process CREATE / EDIT header blocks
        header_pattern = re.compile(r"^\s*(?:CREATE|EDIT)\s+(.+?)$", re.MULTILINE)
        for match in header_pattern.finditer(script_text):
            target_str = match.group(1).strip()
            start_pos = match.end()

            block_start = script_text.find("```", start_pos)
            if block_start == -1:
                continue

            code_start = script_text.find("\n", block_start)
            if code_start == -1:
                continue
            code_start += 1

            block_end = script_text.find("```", code_start)
            if block_end != -1:
                code_body = script_text[code_start:block_end]
            else:
                block_end = script_text.find(SCRIPT_DELIMITER, code_start)
                if block_end != -1:
                    code_body = script_text[code_start:block_end]
                else:
                    code_body = script_text[code_start:]

            code_body = code_body.strip()
            # Clean up trailing stream delimiters if caught in EOF block
            code_body = re.sub(r"=^-\.-^=$", "", code_body).strip()

            target_path = self._resolve_target_file_path(target_str)
            if target_path and self.executor.write_file(str(target_path), code_body):
                modified.append(str(target_path))

        return modified


    def run_target_file(
        self, filepath: str, modified_files: Optional[List[str]] = None
    ) -> ScriptIntakeResult:
        path = Path(filepath)
        ext = path.suffix.lower()
        dispatch = LANG_DISPATCH.get(ext)

        # Default to python interpreter for .tmp or extensionless target scripts
        if dispatch:
            cmd = dispatch["file_cmd"](filepath)
        else:
            cmd = [sys.executable, filepath]

        return self._exec_cmd(cmd, modified_files or [filepath])

    def run_raw_string(
        self,
        code_str: str,
        lang_ext: str = ".py",
        modified_files: Optional[List[str]] = None,
    ) -> ScriptIntakeResult:
        dispatch = LANG_DISPATCH.get(lang_ext, LANG_DISPATCH[".py"])
        cmd = dispatch["eval_cmd"](code_str)
        return self._exec_cmd(cmd, modified_files or [])

    def _exec_cmd(
        self, cmd: List[str], modified_files: List[str]
    ) -> ScriptIntakeResult:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=15,
                cwd=str(self.repo_path),
            )
            return ScriptIntakeResult(
                success=(proc.returncode == 0),
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                modified_files=modified_files,
            )
        except subprocess.TimeoutExpired:
            return ScriptIntakeResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="Script execution timed out (15s limit).",
                modified_files=modified_files,
            )
        except Exception as e:
            return ScriptIntakeResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr=str(e),
                modified_files=modified_files,
            )
