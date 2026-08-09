#!/usr/bin/env python3
# tests/test_engine.py

import json
import pytest
from unittest.mock import MagicMock, patch
from engine.anchor_patch import AnchorPatcher
from engine.working_memory import WorkingMemoryPipeline, ThoughtFrame
from engine.redis_store import RedisMemoryStore
from reasoning.embedder import FeatureEmbedder


def test_anchor_patcher_comprehensive():
    patcher = AnchorPatcher()
    assert patcher._detect_language("script.py") == "python"
    assert patcher._detect_language("config.nix") == "nix"
    assert patcher._detect_language("deploy.sh") == "bash"
    assert patcher._detect_language("unknown.foo") == "text"

    assert patcher._validate_syntax(".py", "def compute():\n    return True\n") is True
    assert patcher._validate_syntax(".py", "Conversational prose...") is False
    assert patcher._validate_syntax(".nix", "{ pkgs, ... }: {\n}\n") is True


@patch("engine.redis_store.redis.Redis")
def test_redis_memory_store_operations(mock_redis_client):
    # Setup mock redis behavior with clean, explicit byte payloads
    mock_instance = mock_redis_client.return_value
    mock_instance.ping.return_value = True
    mock_instance.set.return_value = True
    
    sample_frame = ThoughtFrame(
        session_id="test_sess_01",
        instruction="Initialize vector index and test payload",
        extracted_code="print('hello redis')",
        language="python",
        verification_passed=True
    )
    mock_instance.get.return_value = sample_frame.to_redis_payload().encode("utf-8")

    store = RedisMemoryStore(host="127.0.0.1", port=6379)
    
    store.save_thought_frame(sample_frame)
    retrieved = store.retrieve_thought_frame("test_sess_01")
    assert retrieved is not None
    assert retrieved.session_id == "test_sess_01"


def test_working_memory_pipeline():
    pipeline = WorkingMemoryPipeline()
    frame = pipeline.record_frame(
        instruction="Refactor memory module state stores",
        raw_response="def store_state(): pass",
        filepath="src/engine/redis_store.py",
        code="def store_state(): pass",
        reasoning_plan="1. Define state function\n2. Persist to Redis",
    )
    assert isinstance(frame, ThoughtFrame)
    assert frame.language == "python"
    assert "neural_trace" in frame.reasoning_plan


def test_feature_embedder():
    embedder = FeatureEmbedder()
    if embedder:
        vec = embedder.encode("Test feature embedding generation pipeline")
        assert len(vec) > 0
