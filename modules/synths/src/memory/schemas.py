# src/memory/schemas.py
import time
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field


class LineDiff(BaseModel):
    start_line: int = 0
    end_line: int = 0
    added_lines_count: int = 0
    removed_lines_count: int = 0
    hunk_content: str = ""


class EditPayload(BaseModel):
    original_content: str = ""
    updated_content: str = ""
    diffs: List[LineDiff] = Field(default_factory=list)
    search_blocks_count: int = 0
    symbols_modified: List[str] = Field(default_factory=list)
    original_line_count: int = 0
    updated_line_count: int = 0
    lines_added: int = 0
    lines_removed: int = 0


class CreationPayload(BaseModel):
    created_content: str = ""
    total_lines_created: int = 0
    created_symbols: List[str] = Field(default_factory=list)
    is_fuzzy_redirect: bool = False
    original_requested_path: Optional[str] = None
    file_bytes: int = 0


class ThoughtFrame(BaseModel):
    model_config = ConfigDict(extra="allow")

    session_id: str
    intent_type: str = "patch"  # "CREATE" | "EDIT_EXACT" | "EDIT_FUZZY_APPEND" | "code_execution"
    target_file: str
    language: str = "python"
    instruction: Optional[str] = None
    extracted_code: Optional[str] = None
    verification_passed: bool = True
    payload_type: str = "CREATE"  # "CREATE" | "EDIT"
    payload: Optional[Union[CreationPayload, EditPayload, Dict[str, Any]]] = None
    edit_payload: Optional[EditPayload] = None
    creation_payload: Optional[CreationPayload] = None
    vector: List[float] = Field(default_factory=list)
    ast_facts: Dict[str, Any] = Field(default_factory=dict)
    raw_prompt: str
    timestamp: float = Field(default_factory=time.time)

    # Semantic prediction fields required by WorkingMemoryPipeline & GraphLinker
    predicted_title: Optional[str] = None
    semantic_summary: Optional[str] = None
    concept_tags: List[str] = Field(default_factory=list)

    def to_redis_payload(self) -> str:
        """Serializes the ThoughtFrame model into a JSON string for Redis storage."""
        return self.model_dump_json()
