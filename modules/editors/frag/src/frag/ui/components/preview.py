from rich.syntax import Syntax
from textual.widgets import Static


class BlockPreview(Static):
    """Widget rendering highlighted code without bright backgrounds."""

    def update_view(self, content: str, language: str = "python", line_start: int = 1):
        syntax = Syntax(
            content,
            lexer=language,
            theme="monokai",
            line_numbers=True,
            start_line=line_start,
            word_wrap=False,
            background_color="#121212",
        )
        self.update(syntax)


class TargetPreviewPanel(Static):
    """Contextual preview box displaying selected block metadata and snippets."""

    def update_target(self, block, language: str = "python"):
        if not block:
            self.update("[dim #888888]No target block selected[/dim #888888]")
            return
        lines = f"L{getattr(block, 'start_line', '?')}-L{getattr(block, 'end_line', '?')}"
        snippet_lines = block.content.splitlines()[:3]
        snippet_text = "\n".join(snippet_lines)
        if len(block.content.splitlines()) > 3:
            snippet_text += "\n..."
        self.update(
            f"[bold #00d7ff]Target [{block.index}]:[/bold #00d7ff] {block.name} ({lines})\n[#a0a0a0]{snippet_text}[/#a0a0a0]"
        )
