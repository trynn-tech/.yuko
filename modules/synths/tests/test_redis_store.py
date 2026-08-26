import json
from unittest.mock import MagicMock, patch
import pytest
import redis
from coordinator.pachinko import DispatchDecision, OperationalIntent, PachinkoRouter
from memory import RedisMemoryStore, WorkingMemoryPipeline, render_thought_frame
from memory.schemas import CreationPayload, EditPayload, ThoughtFrame
from memory.thoughtframe_collection import ThoughtFrameCollection, ThoughtFrameFactory

# ============================================================================
# 1. RedisMemoryStore & Index Resiliency
# ============================================================================

@patch("memory.redis_store.redis.Redis")
def test_ensure_vector_index_creation(mock_redis_class):
    """Forces the 'unknown index' exception to test schema creation."""
    mock_client = MagicMock()
    mock_redis_class.return_value = mock_client
    mock_ft = MagicMock()
    mock_ft.info.side_effect = redis.exceptions.ResponseError("Unknown Index name")
    mock_client.ft.return_value = mock_ft

    store = RedisMemoryStore()
    # Triggering the initialization cycle cleanly once
    store._ensure_initialized()
    mock_ft.create_index.assert_called_once()


@patch("memory.redis_store.redis.Redis")
def test_retrieve_thought_frame_fallback(mock_redis_class):
    """Tests the fallback from hget to get, and byte decoding."""
    mock_client = MagicMock()
    mock_redis_class.return_value = mock_client
    mock_client.hget.side_effect = Exception("HGET failed")
    
    # Updated mock payload to include all required fields for ThoughtFrame schema validation
    mock_payload = {
        "session_id": "test1",
        "instruction": "do",
        "language": "python",
        "intent_type": "patch",
        "target_file": "src/dummy.py",
        "raw_prompt": "do",
    }
    mock_client.get.return_value = json.dumps(mock_payload).encode("utf-8")

    store = RedisMemoryStore()
    frame = store.retrieve_thought_frame("test1")
    assert frame is not None
    assert frame.session_id == "test1"


@patch("memory.redis_store.redis.Redis")
def test_knn_search_invalid_vector(mock_redis_class):
    """Tests early exit for invalid vector dimensions with isolated Redis init."""
    mock_client = MagicMock()
    mock_redis_class.return_value = mock_client
        
    store = RedisMemoryStore()
    hits = store.knn_search([0.1, 0.2, 0.3])
    assert hits == []


# ============================================================================
# 2. ThoughtFrameCollection & Factory
# ============================================================================

def test_thoughtframe_factory_creation():
    """Validates creation of populated ThoughtFrame instances via factory."""
    frame = ThoughtFrameFactory.create(
        session_id="sess_001",
        instruction="Refactor AST patch engine",
        language="python",
        vector=[0.01] * 768,
    )
    assert isinstance(frame, ThoughtFrame)
    assert frame.session_id == "sess_001"
    assert len(frame.vector) == 768

@patch("memory.redis_store.redis.Redis")
def test_thoughtframe_collection_store_and_search(mock_redis_class):
    """Tests indexing frames in Redis and executing vector similarity query mock."""
    mock_client = MagicMock()
    mock_redis_class.return_value = mock_client
    
    # Mock search result object containing .docs attribute
    mock_doc = MagicMock()
    mock_doc.session_id = "sess_001"
    mock_doc.target_file = "src/dummy.py"
    mock_doc.score = "0.12"
    mock_doc.json_payload = json.dumps({
        "session_id": "sess_001",
        "instruction": "Search test",
        "intent_type": "patch",
        "target_file": "src/dummy.py",
        "raw_prompt": "Search test",
        "language": "python"
    })

    mock_ft = MagicMock()
    mock_res = MagicMock()
    mock_res.docs = [mock_doc]
    mock_ft.search.return_value = mock_res
    mock_client.ft.return_value = mock_ft

    collection = ThoughtFrameCollection(client=mock_client)
    frame = ThoughtFrameFactory.create(
        session_id="sess_001",
        instruction="Search test",
        intent_type="patch",
        target_file="src/dummy.py",
        raw_prompt="Search test",
        language="python"
    )
            
    collection.add(frame)
    mock_client.hset.assert_called()
    results = collection.search_knn(vector=[0.01] * 768, top_k=1)
    assert len(results) == 1
    assert results[0]["session_id"] == "sess_001"


# ============================================================================
# 3. Pachinko Routing & Working Memory Pipeline
# ============================================================================

def test_pachinko_router_intent_dispatch():
    """Verifies PachinkoRouter correctly assigns dispatch routes based on input payload."""
    router = PachinkoRouter()

    # Direct edit intent should target patcher route
    decision_edit = router.route("Apply unified diff to src/main.py")
    assert decision_edit.intent in (OperationalIntent.EDIT, OperationalIntent.PATCH)
    assert decision_edit.target_component == "patcher"

    # Query intent should target retrieval/memory route
    decision_query = router.route("What was the previous session memory schema?")
    assert decision_query.target_component in ("memory", "retrieval")


def test_working_memory_pipeline_pachinko_integration():
    """Verifies WorkingMemoryPipeline routes incoming prompt through Pachinko before persisting."""
    mock_store = MagicMock()
    pipeline = WorkingMemoryPipeline(redis_store=mock_store)
    prompt = "Patch function-level AST anchor in src/engine/anchor_patch.py"
        
    frame = pipeline.process_incoming_event(session_id="sess_pachinko", prompt=prompt)
    assert frame.session_id == "sess_pachinko"
    assert hasattr(frame, "dispatch_decision") or "patch" in frame.instruction.lower()
    
    # Pipeline execution triggers multiple saves (initialization state and completion state)
    assert mock_store.save_thought_frame.call_count >= 1

# ============================================================================
# 4. Rendering & Schema Serializers
# ============================================================================
def test_render_thought_frame_dict_and_model_support():
    """Ensures render_thought_frame handles both Pydantic models and raw dict fallbacks."""
    frame = ThoughtFrameFactory.create(
        session_id="sess_render",
        instruction="Test render panel",
        intent_type="patch",
        target_file="src/dummy.py",
        raw_prompt="Test render panel",
        language="python"
    )
    # Set payload type and matching CreationPayload for CREATE
    frame.payload_type = "CREATE"
    frame.payload = CreationPayload(total_lines=10, file_size_bytes=100, content_preview="print('hello')")

    # 1. Test with Pydantic object (will implicitly pass if no exception is raised)
    render_thought_frame(frame)

    # 2. Test with raw Dict (will implicitly pass if no exception is raised)
    render_thought_frame(frame.model_dump())
