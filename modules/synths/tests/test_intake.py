#!/usr/bin/env python3
# tests/test_intake.py

from pathlib import Path
import pytest

from engine.executor import Executor
from engine.intake import SCRIPT_DELIMITER, ScriptStreamHandler


@pytest.fixture
def test_env(tmp_path):
    executor = Executor(repo_path=tmp_path)
    handler = ScriptStreamHandler(executor=executor, repo_path=tmp_path)
    return executor, handler, tmp_path


def test_strip_delimiters(test_env):
    _, handler, _ = test_env
    raw = f"{SCRIPT_DELIMITER}\nprint('hello')\n{SCRIPT_DELIMITER}"
    cleaned = handler.strip_delimiters(raw)
    assert cleaned == "print('hello')"


def test_declarative_ops_create_and_delete(test_env):
    _, handler, tmp_path = test_env

    # 1. Test CREATE directive
    stream = """CREATE sample.py
```python
print("created file")
```"""
    handler.process_stream(stream)
    created_file = tmp_path / "sample.py"
    assert created_file.exists()
    assert "created file" in created_file.read_text()

    # 2. Test DELETE directive
    delete_stream = "DELETE sample.py"
    handler._parse_and_apply_declarative_ops(delete_stream)
    assert not created_file.exists()

import textwrap


def test_process_stream_execution(test_env):
    _, handler, tmp_path = test_env
    stream = textwrap.dedent(
        f"""\
        {SCRIPT_DELIMITER}
        CREATE runner.py
        ```python
        # target: runner.py
        print("Intake Executed Successfully")
        ```
        {SCRIPT_DELIMITER}
        """
    )

    result = handler.process_stream(stream)
    assert result.success, f"Intake execution failed with stderr:\n{result.stderr}"
    assert result.returncode == 0
    assert "Intake Executed Successfully" in result.stdout.strip()
