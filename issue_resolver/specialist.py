"""Specialist Agents — BugFixer, FeatureDev, Refactorer.

Phase 3 implementation. This file is a stub skeleton.
"""
from .agent_base import AgentBase
from .context import IssueContext


class SpecialistBase(AgentBase):
    """Base for all specialist agents. Phase 3 will implement language detection,
    affected_files enforcement, and test execution.
    """
    allowed_tools: list[str] = ["Read", "Edit", "Write", "Bash", "Grep", "Glob"]

    async def run(self, ctx: IssueContext) -> IssueContext:
        raise NotImplementedError("SpecialistBase.run() — implemented in Phase 3")


class BugFixerAgent(SpecialistBase):
    """Fixes bugs within affected_files scope. Phase 3 implementation."""


class FeatureDevAgent(SpecialistBase):
    """Implements new features with tests. Phase 3 implementation."""


class RefactorerAgent(SpecialistBase):
    """Performs code refactoring. Phase 3 implementation."""
