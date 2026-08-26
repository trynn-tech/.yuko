#!/usr/bin/env python3
# src/engine/verifier.py

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from rich.console import Console

console = Console()


class VerificationHook:
    """Executes test suites with coverage (pytest-cov) and evaluates code health
    in real-time using Rich live streaming as part of the neuro-symbolic feedback loop.
    """

    def __init__(self, root_path: Optional[Path] = None):
        if root_path is None:
            cwd = Path.cwd().resolve()
            if cwd.name == "tests":
                self.root_path = cwd.parent
            else:
                self.root_path = cwd
        else:
            self.root_path = root_path.resolve()

    def run_coverage_check(
        self, target_file: str, test_path: str = "tests"
    ) -> Dict[str, Any]:
        """Runs pytest with live streaming via Rich status spinner and real-time output parsing."""
        results: Dict[str, Any] = {
            "tests_passed": False,
            "coverage_pct": 0.0,
            "uncovered_lines": [],
            "error_output": "",
        }
        target_test_dir = self.root_path / test_path
        if not target_test_dir.exists():
            results["tests_passed"] = False
            results["error_output"] = f"Test directory '{test_path}' not found."
            return results

        rcfile_path = self.root_path / "src" / "engine" / ".coveragerc"
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(target_test_dir),
            "-v",
            "--cov=src",
            f"--cov-config={rcfile_path}",
            "--cov-report=json",
            "--cov-report=term",
            "-q",
        ]

        env = dict(os.environ)
        src_path = str(self.root_path / "src")
        existing_pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{src_path}:{existing_pp}" if existing_pp else src_path

        console.print("[cyan]▶ Streaming Pytest Suite & Coverage Audit...[/cyan]")
        
        passed = True
        try:
            with console.status("[bold yellow]Executing test suite live...", spinner="dots"):
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    cwd=str(self.root_path),
                    env=env,
                )

                if process.stdout is not None:
                    for line in process.stdout:
                        line_str = line.strip()
                        if line_str:
                            if "PASSED" in line_str or "✔" in line_str:
                                console.print(f"  [green]✔[/green] {line_str}")
                            elif "FAILED" in line_str or "ERROR" in line_str:
                                console.print(f"  [bold red]✖ {line_str}[/bold red]")
                                passed = False
                            elif "====" in line_str or "coverage:" in line_str:
                                console.print(f"  [bold cyan]{line_str}[/bold cyan]")
                            else:
                                console.print(f"    [dim]{line_str}[/dim]")

                process.wait()
                if process.returncode != 0:
                    passed = False

            results["tests_passed"] = passed

            cov_file = self.root_path / "coverage.json"
            if cov_file.exists():
                cov_data = json.loads(cov_file.read_text(encoding="utf-8"))
                totals = cov_data.get("totals", {})
                results["coverage_pct"] = float(totals.get("percent_covered", 0.0))

        except subprocess.TimeoutExpired:
            results["tests_passed"] = False
            results["error_output"] = "Test execution timed out."
        except Exception as e:
            results["tests_passed"] = False
            results["error_output"] = str(e)

        return results
