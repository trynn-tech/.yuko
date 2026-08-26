#!/usr/bin/env python3
# tests/test_executor_graph.py

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from engine.executor import Executor
from reasoning.graph_linker import KnowledgeGraphLinker


class DummyStep:
    """Mock architecture step object for testing."""
    def __init__(self, target_file, search, replace):
        self.target_file = target_file
        self.search = search
        self.replace = replace


@pytest.fixture
def temp_repo(tmp_path):
    """Provides a clean temporary directory simulating a repo context."""
    return tmp_path


# ==========================================
# EXECUTOR TEST SUITE
# ==========================================

def test_executor_run_edit_pass_positional(temp_repo):
    """Tests run_edit_pass using explicit positional args (filepath, search, replace)."""
    executor = Executor(repo_path=temp_repo)
    target = temp_repo / "positional.py"
    success = executor.run_edit_pass(str(target), "", "def foo():\n    pass\n")
    assert success is True
    assert target.read_text() == "def foo():\n    pass\n"


def test_executor_run_edit_pass_dict(temp_repo):
    """Tests run_edit_pass using a dictionary payload."""
    executor = Executor(repo_path=temp_repo)
    target = temp_repo / "dict.py"
    payload = {
        "target_file": str(target),
        "search": "",
        "replace": "print('hello world')"
    }
    success = executor.run_edit_pass(payload)
    assert success is True
    assert target.read_text() == "print('hello world')"


def test_executor_run_edit_pass_object(temp_repo):
    """Tests run_edit_pass using a mock Step object."""
    executor = Executor(repo_path=temp_repo)
    target = temp_repo / "object.py"
    step = DummyStep(str(target), "", "x = 42\n")
    success = executor.run_edit_pass(step)
    assert success is True
    assert target.read_text() == "x = 42\n"


@patch("engine.executor.AnchorPatcher")
def test_executor_run_edit_pass_raw_string(MockPatcher, temp_repo):
    """Tests run_edit_pass interpreting a raw string block via AnchorPatcher."""
    mock_instance = MockPatcher.return_value
    mock_block = MagicMock()
    mock_block.filepath = str(temp_repo / "string_generated.py")
    mock_block.search_anchor = ""
    mock_block.replace_block = "class RawString:\n    pass\n"
    mock_instance.parse_blocks.return_value = [mock_block]

    executor = Executor(repo_path=temp_repo)
    success = executor.run_edit_pass("```python\nclass RawString:\n    pass\n```", fallback_filepath="string_generated.py")
    assert success is True
    assert Path(mock_block.filepath).read_text() == "class RawString:\n    pass\n"


def test_executor_fuzzy_splice_fallback(temp_repo):
    """Tests the indentation-insensitive fuzzy line matching algorithm."""
    target = temp_repo / "fuzzy.py"
    initial_content = "def setup():\n    pass\n\ndef teardown():\n    pass\n"
    target.write_text(initial_content)
    
    executor = Executor(repo_path=temp_repo)
    executor.has_sd = False
    
    search_anchor = "def teardown():\npass"
    replace_block = "def teardown():\n    print('cleaned')\n    pass"
    
    # Corrected: Unpack tuple return (success, line_range) from _apply_fuzzy_splice
    success, line_range = executor._apply_fuzzy_splice(
        target, target.read_text(), search_anchor, replace_block
    )
    assert success is True
    
    new_content = target.read_text()
    assert "print('cleaned')" in new_content
    assert "setup" in new_content


# ==========================================
# KNOWLEDGE GRAPH LINKER TEST SUITE
# ==========================================

@patch("reasoning.graph_linker.GraphDatabase")
def test_graph_init_schema(mock_neo4j):
    """Verifies that schema initialization correctly iterates over Cypher constraints."""
    mock_driver = MagicMock()
    mock_neo4j.driver.return_value = mock_driver
    mock_session = mock_driver.session.return_value.__enter__.return_value

    linker = KnowledgeGraphLinker()
    success = linker.init_schema()
    assert success is True

    expected_calls = len(linker.SCHEMA_QUERIES) * 2
    actual_calls = mock_session.run.call_count

    assert actual_calls == expected_calls, (
        f"Schema initialization run call count mismatch! "
        f"Expected {expected_calls} calls ({len(linker.SCHEMA_QUERIES)} queries * 2), "
        f"but session.run was called {actual_calls} times."
    )


@patch("reasoning.graph_linker.GraphDatabase")
def test_graph_sync_thought_frame(mock_neo4j):
    """Verifies thought frames resolve AST lists into Neo4j nodes."""
    mock_driver = MagicMock()
    mock_neo4j.driver.return_value = mock_driver
    mock_session = mock_driver.session.return_value.__enter__.return_value

    linker = KnowledgeGraphLinker()
    linker.init_schema()
    mock_session.run.reset_mock()

    frame_data = {
        "resolved_path": "src/engine/executor.py",
        "language": "python",
        "ast_facts": {
            "functions": ["run_edit_pass", "_apply_fuzzy_splice"],
            "classes": ["Executor"]
        },
        "concept_tags": ["file_io", "git_tracking"]
    }

    success = linker.sync_thought_frame_graph(frame_data)
    assert success is True

    cypher_queries = [call[0][0] for call in mock_session.run.call_args_list]
    assert any("MERGE (f:CodeFile" in q for q in cypher_queries)


@patch("reasoning.graph_linker.GraphDatabase")
def test_graph_retrieve_context(mock_neo4j):
    """Verifies standard context queries map records to lists accurately."""
    mock_driver = MagicMock()
    mock_neo4j.driver.return_value = mock_driver
    mock_session = mock_driver.session.return_value.__enter__.return_value

    mock_record = MagicMock()
    mock_record.data.return_value = {
        "file_path": "test.py",
        "language": "python",
        "functions": ["test_fn"],
        "classes": [],
        "matched_tags": ["testing"]
    }
    mock_session.run.return_value = [mock_record]

    linker = KnowledgeGraphLinker()
    results = linker.retrieve_graph_context(["testing"])

    assert "test.py" in results["files"]
    assert "test_fn" in results["functions"]
    assert "testing" in results["related_tags"]


def test_graph_missing_neo4j_graceful_fail():
    """Verifies the system degrades gracefully when Neo4j connections fail."""
    linker = KnowledgeGraphLinker(uri="bolt://invalid-host:9999")
    success = linker.init_schema()
    assert success is False

    results = linker.retrieve_graph_context(["fallback"])
    assert results["files"] == []
