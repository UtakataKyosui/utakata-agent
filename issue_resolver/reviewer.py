"""Reviewer Agent — reviews changes before PR creation.

Phase 4 implementation. This file is a stub skeleton.
"""
from .agent_base import AgentBase
from .context import IssueContext


class ReviewerAgent(AgentBase):
    """Reviews changes for quality, security, and scope. Phase 4 will implement:
    diff audit, bandit integration, review_passed output.
    """
    allowed_tools: list[str] = ["Read", "Grep", "Bash"]

    async def run(self, ctx: IssueContext) -> IssueContext:
        raise NotImplementedError("ReviewerAgent.run() — implemented in Phase 4")
