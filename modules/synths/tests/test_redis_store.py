import pytest
from unittest.mock import patch, MagicMock
from engine.redis_store import RedisMemoryStore, HAS_REDISEARCH
import redis

@patch("engine.redis_store.redis.Redis")
def test_ensure_vector_index_creation(mock_redis_class):
    """Forces the 'unknown index' exception to test schema creation."""
    mock_client = MagicMock()
    mock_redis_class.return_value = mock_client
    
    # Make the first call to ft().info() raise an unknown index error
    mock_ft = MagicMock()
    mock_ft.info.side_effect = redis.exceptions.ResponseError("Unknown Index name")
    mock_client.ft.return_value = mock_ft
    
    store = RedisMemoryStore()
    store._get_client() # Triggers ping and _ensure_vector_index
    
    # Assert create_index was called
    mock_ft.create_index.assert_called_once()
    assert store._index_initialized is True

@patch("engine.redis_store.redis.Redis")
def test_retrieve_thought_frame_fallback(mock_redis_class):
    """Tests the fallback from hget to get, and byte decoding."""
    mock_client = MagicMock()
    mock_redis_class.return_value = mock_client
    
    # Simulate hget failing or returning None, forcing fallback to get()
    mock_client.hget.side_effect = Exception("HGET failed")
    # Simulate get() returning raw bytes
    mock_client.get.return_value = b'{"session_id": "test1", "instruction": "do", "language": "python"}'
    
    store = RedisMemoryStore()
    frame = store.retrieve_thought_frame("test1")
    
    assert frame is not None
    assert frame.session_id == "test1"

def test_knn_search_invalid_vector():
    """Tests early exit for invalid vector dimensions."""
    store = RedisMemoryStore()
    # Provide a vector of length 3 instead of 768
    hits = store.knn_search([0.1, 0.2, 0.3])
    assert hits == []
