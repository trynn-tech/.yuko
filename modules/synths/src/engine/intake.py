#!/usr/bin/env python3
# modules/synths/src/engine/intake.py

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


class ScriptIntakeResult:
    """Holds the result of a script intake execution pass."""

    def __init__(
        self,
        success: bool,
        returncode: int,
        stdout: str,
        stderr: str,
        modified_files: List[str],
    ):
        self.success = success
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.modified_files = modified_files

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "modified_files": self.modified_files,
        }


class ScriptStreamHandler:
    """Handles parsing and execution for stdin/script intake mode (-s / =^-.-^=).
    Decouples stream reading and subprocess execution from atomic file editing.
    """

    def __init__(self, executor: Any, repo_path: Optional[Path] = None):
        self.executor = executor
        self.repo_path = (repo_path or Path.cwd()).resolve()

    def process_stream(self, raw_stream_content: str) -> ScriptIntakeResult:
        """Parses the intake stream, applies file operations, and executes the script target."""
        clean_content = self.strip_delimiters(raw_stream_content)
        modified_files: List[str] = []

        # 1. Process explicit CREATE / DELETE directives embedded in intake stream
        created_files = self._parse_and_apply_declarative_ops(clean_content)
        modified_files.extend(created_files)

        # 2. Check if intake contains SEARCH / REPLACE blocks or code fences
        default_target = "main.py"
        blocks = self.executor.patcher.parse_blocks(
            clean_content, fallback_filepath=default_target
        )
        if blocks:
            for block in blocks:
                raw_filepath = (
                    block.filepath if block.filepath.strip() else default_target
                )
                target_path = Path(raw_filepath)
                if target_path.is_dir():
                    target_path = target_path / default_target
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

        # 3. Determine execution strategy: run target file or raw script string
        runnable_code, target_file = self._extract_runnable_target(clean_content)
        if target_file and runnable_code:
            self.executor.write_file(target_file, runnable_code)
            if target_file not in modified_files:
                modified_files.append(target_file)
            return self.run_python_file(target_file, modified_files=modified_files)

        # If modified Python files exist (e.g., created via CREATE directive), execute the primary target file
        py_files = [f for f in modified_files if f.endswith(".py")]
        if py_files:
            return self.run_python_file(py_files[0], modified_files=modified_files)

        # Fall back to raw string execution - strip CREATE/DELETE and markdown code fences
        sanitized_code = re.sub(
            r"^\s*(?:CREATE|DELETE)\s+.*$", "", clean_content, flags=re.MULTILINE
        ).strip()
        sanitized_code = self._strip_code_fences(sanitized_code)
        return self.run_raw_string(sanitized_code, modified_files=modified_files)

    def strip_delimiters(self, text: str) -> str:
        """Strips leading and trailing =^-.-^= intake delimiters."""
        cleaned = text.strip()
        if cleaned.startswith(SCRIPT_DELIMITER):
            cleaned = cleaned[len(SCRIPT_DELIMITER) :].lstrip()
        if cleaned.endswith(SCRIPT_DELIMITER):
            cleaned = cleaned[: -len(SCRIPT_DELIMITER)].rstrip()
        return cleaned

    def _strip_code_fences(self, text: str) -> str:
        """Strips surrounding ``` or ```python markdown blocks for raw string execution."""
        lines = text.strip().splitlines()
        if lines and re.match(r"^\s*```[a-zA-Z0-9_-]*\s*$", lines[0]):
            lines = lines[1:]
        if lines and re.match(r"^\s*```\s*$", lines[-1]):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    def _parse_and_apply_declarative_ops(self, script_text: str) -> List[str]:
        """Parses CREATE <path> and DELETE <path> blocks out of the intake stream."""
        modified = []
        # Handle DELETE directives
        for match in re.finditer(r"^\s*DELETE\s+(.+)$", script_text, re.MULTILINE):
            target_path = self.repo_path / match.group(1).strip()
            if target_path.exists():
                try:
                    target_path.unlink()
                    modified.append(str(target_path))
                except OSError as e:
                    console.print(
                        f"[red]Failed to delete {target_path.name}:[/red] {e}"
                    )

        # Handle CREATE directives (flexible on inline vs newline code fences)
        create_pattern = re.compile(
            r"^\s*CREATE\s+(.+?)\s*[\n\r]*```(?:[a-zA-Z0-9_-]+)?[\n\r]+(.*?)\n```",
            re.MULTILINE | re.DOTALL,
        )
        for match in create_pattern.finditer(script_text):
            target_str = match.group(1).strip()
            code_body = match.group(2)
            if self.executor.write_file(target_str, code_body):
                modified.append(target_str)
        return modified

    def _extract_runnable_target(
        self, script_text: str
    ) -> Tuple[Optional[str], Optional[str]]:
        """Extracts code block content and explicit # target: file.py annotations."""
        match = re.search(
            r"```(?:python)?[\n\r]+(.*?)\n```", script_text, re.DOTALL | re.IGNORECASE
        )
        if match:
            code = match.group(1)
            target_match = re.search(r"#\s*target:\s*([^\n]+)", code)
            target_file = target_match.group(1).strip() if target_match else None
            return code, target_file
        return None, None

    def run_python_file(
        self, filepath: str, modified_files: Optional[List[str]] = None
    ) -> ScriptIntakeResult:
        """Executes a target python script with a 15-second subshell timeout."""
        cmd = [sys.executable, filepath]
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
                modified_files=modified_files or [filepath],
            )
        except subprocess.TimeoutExpired:
            return ScriptIntakeResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr="Script execution timed out (15s limit).",
                modified_files=modified_files or [filepath],
            )
        except Exception as e:
            return ScriptIntakeResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr=str(e),
                modified_files=modified_files or [filepath],
            )

    def run_raw_string(
        self, code_str: str, modified_files: Optional[List[str]] = None
    ) -> ScriptIntakeResult:
        """Executes raw string code directly via `python -c`."""
        cmd = [sys.executable, "-c", code_str]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            return ScriptIntakeResult(
                success=(proc.returncode == 0),
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                modified_files=modified_files or [],
            )
        except Exception as e:
            return ScriptIntakeResult(
                success=False,
                returncode=-1,
                stdout="",
                stderr=str(e),
                modified_files=modified_files or [],
            )
