"""Analyzer Agent — reads Issue and identifies affected files.

Phase 2 implementation. This file is a stub skeleton.
"""
from .agent_base import AgentBase
from .context import IssueContext


class AnalyzerAgent(AgentBase):
    """Analyzes a GitHub Issue and populates IssueContext.analyzer_output fields.

    Phase 2 will implement: issue type detection, codebase exploration,
    affected_files identification, complexity scoring.
    """
    allowed_tools: list[str] = ["Read", "Grep", "Glob"]

    async def run(self, ctx: IssueContext) -> IssueContext:
        """Run analysis. Raises NotImplementedError until Phase 2."""
        raise NotImplementedError("AnalyzerAgent.run() — implemented in Phase 2")
