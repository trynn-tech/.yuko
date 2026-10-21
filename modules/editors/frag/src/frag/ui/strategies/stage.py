from typing import Dict, List, Optional
from ..base import BaseEditorStrategy

class StageStrategy(BaseEditorStrategy):
    """Manages multi-stage refactoring assignments and classification groups."""

    def assign_stage(self, stage_id: int, block_id: Optional[int]) -> None:
        if block_id is None or block_id == 0:
            return

        block = next((b for b in self.frag.blocks if b.index == block_id), None)
        if not block:
            return

        block.stage_id = stage_id

        if hasattr(self.frag, "stages"):
            if stage_id not in self.frag.stages:
                self.frag.stages[stage_id] = []
            if block_id not in self.frag.stages[stage_id]:
                self.frag.stages[stage_id].append(block_id)

        if hasattr(self.app, "navigation_strategy"):
            self.app.navigation_strategy.populate_tree()

        self.app.log_status(
            f"[bold #00d7ff]Assigned Block [{block_id}] -> Stage {stage_id}[/bold #00d7ff]"
        )

    def get_stage_blocks(self, stage_id: int) -> List[int]:
        if hasattr(self.frag, "stages"):
            return self.frag.stages.get(stage_id, [])
        return [b.index for b in self.frag.blocks if getattr(b, "stage_id", None) == stage_id]
