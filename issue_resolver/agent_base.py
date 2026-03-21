"""Base class for all issue-resolver pipeline agents.

All agents (Analyzer, BugFixer, FeatureDev, Refactorer, Reviewer) inherit from AgentBase.
Provides: bypassPermissions, allowed_tools, SubagentStart/SubagentStop logging hooks.
"""
import asyncio
from datetime import datetime, timezone
from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    HookMatcher,
)


class AgentBase:
    """Base class for all pipeline agents.

    Subclasses MUST override `allowed_tools` with the tools their agent needs.
    Use `_make_options()` to get a ClaudeAgentOptions instance with hooks pre-configured.
    """

    allowed_tools: list[str] = []

    def _make_options(self, extra_mcp_servers: dict | None = None) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions with bypassPermissions + logging hooks."""
        return ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            allowed_tools=self.allowed_tools,
            hooks={
                "SubagentStart": [HookMatcher(hooks=[self._on_subagent_start])],
                "SubagentStop": [HookMatcher(hooks=[self._on_subagent_stop])],
            },
            mcp_servers=extra_mcp_servers or {},
        )

    async def _on_subagent_start(self, input, tool_use_id, context):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"[{ts}] [{self.__class__.__name__}] SubagentStart agent_id={input.get('agent_id')} type={input.get('agent_type')}")
        return {"continue_": True}

    async def _on_subagent_stop(self, input, tool_use_id, context):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"[{ts}] [{self.__class__.__name__}] SubagentStop agent_id={input.get('agent_id')} type={input.get('agent_type')}")
        return {"continue_": True}
