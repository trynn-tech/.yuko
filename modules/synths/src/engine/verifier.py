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
    """
    Executes test suites with coverage (pytest-cov) and evaluates code health
    as part of the neuro-symbolic feedback loop using the hermetic Python interpreter.
    """

    def __init__(self, root_path: Optional[Path] = None):
        self.root_path = (root_path or Path.cwd()).resolve()

    def run_coverage_check(self, target_file: str, test_path: str = "tests") -> Dict[str, Any]:
        """Runs pytest with coverage pointing explicitly to the test suite directory with PYTHONPATH set."""
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

        try:
            cmd = [
                sys.executable,
                "-m",
                "pytest",
                str(target_test_dir),
                "--cov=src",
                "--cov-report=json",
                "-q",
            ]
            
            # Inject src into PYTHONPATH so coverage tracks modules correctly
            env = dict(os.environ)
            src_path = str(self.root_path / "src")
            existing_pp = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{src_path}:{existing_pp}" if existing_pp else src_path

            res = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(self.root_path),
                env=env,
                timeout=30,
            )

            output_lower = res.stdout.lower()
            no_tests_ran = "no tests ran" in output_lower or "collected 0 items" in output_lower

            if res.returncode == 0 and not no_tests_ran:
                results["tests_passed"] = True
            else:
                results["tests_passed"] = False
                results["error_output"] = res.stderr.strip() or res.stdout.strip()
                if no_tests_ran and not results["error_output"]:
                    results["error_output"] = "Pytest collected 0 test items or no tests were executed."

            cov_file = self.root_path / "coverage.json"
            if cov_file.exists():
                cov_data = json.loads(cov_file.read_text(encoding="utf-8"))
                files_cov = cov_data.get("files", {})

                target_p = Path(target_file)
                try:
                    rel_target = str(
                        target_p.relative_to(self.root_path)
                        if target_p.is_absolute()
                        else target_p
                    )
                except ValueError:
                    rel_target = str(target_file)

                matched_stats = None
                for fpath, stats in files_cov.items():
                    if fpath.endswith(rel_target) or rel_target.endswith(fpath):
                        matched_stats = stats
                        break

                if matched_stats:
                    summary = matched_stats.get("summary", {})
                    results["coverage_pct"] = float(summary.get("percent_covered", 0.0))
                    results["uncovered_lines"] = matched_stats.get("missing_lines", [])
                else:
                    totals = cov_data.get("totals", {})
                    results["coverage_pct"] = float(totals.get("percent_covered", 0.0))

        except subprocess.TimeoutExpired:
            results["tests_passed"] = False
            results["error_output"] = "Test execution timed out."
        except Exception as e:
            results["tests_passed"] = False
            results["error_output"] = str(e)

        return results
