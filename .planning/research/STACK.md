# Technology Stack: claude-agent-sdk Multi-Agent Patterns

**Project:** utakata-agent / issue-resolver workflow
**SDK Version:** claude-agent-sdk 0.1.50
**Researched:** 2026-03-22
**Source:** Direct inspection of installed SDK at `.venv/lib/python3.12/site-packages/claude_agent_sdk/`
**Confidence:** HIGH — all findings are from primary source code, not documentation guesses.

---

## 1. How `AgentDefinition` Works

### Definition (from `types.py`)

```python
@dataclass
class AgentDefinition:
    description: str
    prompt: str
    tools: list[str] | None = None
    model: Literal["sonnet", "opus", "haiku", "inherit"] | None = None
    skills: list[str] | None = None
    memory: Literal["user", "project", "local"] | None = None
    mcpServers: list[str | dict[str, Any]] | None = None
```

### How It Is Passed to the CLI

`AgentDefinition` instances are placed in `ClaudeAgentOptions.agents` as a `dict[str, AgentDefinition]`. When `ClaudeSDKClient.connect()` is called, the dataclasses are converted to dicts (using `dataclasses.asdict`) and sent to the CLI via the `initialize` control-protocol message:

```python
# From client.py connect()
agents_dict = {
    name: {k: v for k, v in asdict(agent_def).items() if v is not None}
    for name, agent_def in self.options.agents.items()
}
# ... passed as request["agents"] in the initialize handshake
```

### Best Practices for Multi-Agent Setup

- Use **`ClaudeSDKClient`** (not `query()`) when defining agents. The initialize handshake that carries the `agents` dict only runs in streaming mode, which `ClaudeSDKClient` always uses.
- Name agents descriptively: the name key becomes the agent type identifier in hook events (`agent_type` field).
- Set `model: "inherit"` for sub-agents that should use whatever model the orchestrator was started with. Set an explicit model only for agents with different cost/capability requirements.
- Fields that are `None` are stripped before sending (the dict comprehension above), so omitting optional fields is safe.
- `mcpServers` in `AgentDefinition` takes server *names* (strings referencing servers already registered in `ClaudeAgentOptions.mcp_servers`), not inline configs.

---

## 2. `query()` vs `ClaudeSDKClient` for Multi-Agent Use Cases

### Authoritative Summary (from `query.py` docstring)

| Dimension | `query()` | `ClaudeSDKClient` |
|-----------|-----------|-------------------|
| Direction | Unidirectional | Bidirectional |
| State | Stateless per call | Stateful session |
| Agent definitions | **NOT supported** | **Supported** (initialize handshake) |
| Hook callbacks | Not supported | Supported |
| Permission callbacks (`can_use_tool`) | Not supported | Supported |
| Interrupt | Not possible | `await client.interrupt()` |
| Follow-up messages | Not possible | `await client.query(prompt)` |
| Connection management | Automatic | Manual (`connect`/`disconnect`) |
| Use case | CI scripts, one-shot analysis | Multi-agent pipelines |

### Recommendation for issue-resolver

**Use `ClaudeSDKClient` exclusively.** The `agents` dict is only sent during the streaming-mode `initialize` handshake. `query()` never calls `initialize()`, so any `agents` config passed via `ClaudeAgentOptions` would be silently ignored.

`query()` is only appropriate for the simplest leaf operations (e.g., a standalone "summarize this text" call that needs no tools and no pipeline context).

### Practical Pattern

```python
options = ClaudeAgentOptions(
    agents={
        "analyzer":   AgentDefinition(description="...", prompt="...", tools=["Read", "Grep"]),
        "bug-fixer":  AgentDefinition(description="...", prompt="...", tools=["Edit", "Bash"]),
        "reviewer":   AgentDefinition(description="...", prompt="...", tools=["Read"]),
        "pr-creator": AgentDefinition(description="...", prompt="...", tools=["Bash"]),
    },
    mcp_servers={"github": github_sdk_server},
    permission_mode="bypassPermissions",
)

async with ClaudeSDKClient(options) as client:
    await client.query(orchestrator_prompt)
    async for msg in client.receive_response():
        ...
```

---

## 3. `SubagentStart` / `SubagentStop` Hooks for Monitoring Parallel Agents

### Hook Input Types (from `types.py`)

```python
class SubagentStartHookInput(BaseHookInput):
    hook_event_name: Literal["SubagentStart"]
    agent_id: str        # Unique ID for this sub-agent invocation
    agent_type: str      # Matches the key name in ClaudeAgentOptions.agents

class SubagentStopHookInput(BaseHookInput):
    hook_event_name: Literal["SubagentStop"]
    stop_hook_active: bool
    agent_id: str
    agent_transcript_path: str   # Path to the sub-agent's full transcript on disk
    agent_type: str
```

Both inherit `BaseHookInput` which provides: `session_id`, `transcript_path`, `cwd`, `permission_mode`.

### Attribution in Parallel Execution

The `_SubagentContextMixin` (mixed into `PreToolUseHookInput`, `PostToolUseHookInput`, `PostToolUseFailureHookInput`, `PermissionRequestHookInput`) adds optional `agent_id` and `agent_type` fields to tool-lifecycle hooks. The SDK docstring explains:

> "When multiple sub-agents run in parallel their tool-lifecycle hooks interleave over the same control channel — this is the only reliable way to attribute each one to the correct sub-agent."

So `agent_id` is the **primary correlation key** for attributing parallel events to a specific sub-agent.

### Registering Hooks

```python
from claude_agent_sdk import HookMatcher, ClaudeAgentOptions

async def on_subagent_start(hook_input, tool_use_id, ctx):
    print(f"Agent started: {hook_input['agent_type']} (id={hook_input['agent_id']})")
    return {"continue_": True}

async def on_subagent_stop(hook_input, tool_use_id, ctx):
    print(f"Agent stopped: {hook_input['agent_type']}, transcript: {hook_input['agent_transcript_path']}")
    return {"continue_": True}

options = ClaudeAgentOptions(
    hooks={
        "SubagentStart": [HookMatcher(hooks=[on_subagent_start])],
        "SubagentStop":  [HookMatcher(hooks=[on_subagent_stop])],
    },
    ...
)
```

### Hook Output: Python vs CLI Field Names

The SDK uses `async_` and `continue_` (with trailing underscores) to avoid Python keyword conflicts. These are automatically converted to `async` and `continue` before being sent to the CLI. Always use the underscore versions in Python code.

### Hook Callback Signature

```python
HookCallback = Callable[
    [HookInput, str | None, HookContext],
    Awaitable[HookJSONOutput]
]
# HookContext is currently {"signal": None} — abort signal support is a TODO in the SDK.
```

---

## 4. Passing Context Between Pipeline Stages

The SDK has no built-in shared memory or pipeline state object. Context must be passed explicitly. Three viable patterns, ordered by simplicity:

### Pattern A: Structured Prompt Injection (recommended for issue-resolver)

Collect output from each stage, format it into the next stage's prompt string.

```python
# Stage 1: Analyzer
analysis_result = ""
await client.query(f"Analyze GitHub issue #{issue_number}: {issue_body}")
async for msg in client.receive_response():
    if isinstance(msg, AssistantMessage):
        for block in msg.content:
            if isinstance(block, TextBlock):
                analysis_result += block.text
    elif isinstance(msg, ResultMessage):
        break

# Stage 2: BugFixer receives the analysis as context
await client.query(f"""
Analysis from previous stage:
{analysis_result}

Now implement the fix. Work in: {cwd}
""")
```

### Pattern B: `output_format` for Structured JSON Output

Use `ClaudeAgentOptions(output_format={"type": "json_schema", "schema": {...}})` to force structured output that is easier to parse and pass between stages.

```python
options = ClaudeAgentOptions(
    output_format={
        "type": "json_schema",
        "schema": {
            "type": "object",
            "properties": {
                "issue_type": {"type": "string"},
                "affected_files": {"type": "array", "items": {"type": "string"}},
                "root_cause": {"type": "string"},
            }
        }
    }
)
```

`ResultMessage.structured_output` carries the parsed result.

### Pattern C: Session Resume

Pass `resume=session_id` in `ClaudeAgentOptions` to continue a previous conversation. Sub-agents spawned in the resumed session have access to the full prior context without explicit injection.

```python
options = ClaudeAgentOptions(resume=previous_session_id)
```

Note: `fork_session=True` can be combined with `resume` to branch from a checkpoint without modifying the original session.

---

## 5. `@tool` Decorator and `create_sdk_mcp_server()` for Custom GitHub Tools

### The `@tool` Decorator

`@tool` is a function decorator (not a class decorator) that creates an `SdkMcpTool` dataclass:

```python
@dataclass
class SdkMcpTool(Generic[T]):
    name: str
    description: str
    input_schema: type[T] | dict[str, Any]
    handler: Callable[[T], Awaitable[dict[str, Any]]]
    annotations: ToolAnnotations | None = None
```

Usage:

```python
from claude_agent_sdk import tool, create_sdk_mcp_server

@tool(
    name="get_github_issue",
    description="Fetch a GitHub issue by number",
    input_schema={"repo": str, "issue_number": int},
)
async def get_github_issue(args: dict) -> dict:
    # args["repo"], args["issue_number"] are available
    # Call GitHub API here
    return {"content": [{"type": "text", "text": issue_json}]}

@tool(
    name="create_pull_request",
    description="Create a GitHub pull request",
    input_schema={"repo": str, "title": str, "body": str, "head": str, "base": str},
)
async def create_pull_request(args: dict) -> dict:
    # Create PR via GitHub API
    return {"content": [{"type": "text", "text": pr_url}]}
```

### `create_sdk_mcp_server()`

Wraps tools in an in-process MCP server. No subprocess overhead — runs in the same Python process.

```python
github_server = create_sdk_mcp_server(
    name="github",
    version="1.0.0",
    tools=[get_github_issue, create_pull_request, ...],
)

options = ClaudeAgentOptions(
    mcp_servers={"github": github_server},
    allowed_tools=["get_github_issue", "create_pull_request", ...],
)
```

### Input Schema Conversion Rules (from SDK source)

The SDK converts the simple dict schema `{"param": type}` to JSON Schema automatically:

| Python type | JSON Schema type |
|-------------|-----------------|
| `str` | `"string"` |
| `int` | `"integer"` |
| `float` | `"number"` |
| `bool` | `"boolean"` |
| anything else | `"string"` (default fallback) |

All keys are marked as `required`. For optional parameters, pass a full JSON Schema dict with `"required": [...]` listing only mandatory fields.

### Error Signaling from Tools

Return `{"content": [...], "is_error": True}` to signal tool failure to the agent without raising a Python exception.

### Current SDK Limitation

The in-process MCP bridge manually routes only `initialize`, `tools/list`, `tools/call`, and `notifications/initialized`. Resource and prompt capabilities are not yet supported. Tools-only servers are fully functional.

---

## 6. `permissionMode` Settings for Autonomous Agents

### Available Values (from `types.py`)

```python
PermissionMode = Literal["default", "acceptEdits", "plan", "bypassPermissions"]
```

### Mode Descriptions (from SDK docstrings)

| Mode | Behavior | Recommended For |
|------|----------|-----------------|
| `"default"` | CLI prompts for dangerous tools | Interactive use only — will block autonomous pipelines |
| `"acceptEdits"` | Auto-accepts file edits | Agents that write/modify files but should not run arbitrary shell commands |
| `"plan"` | Planning mode, no execution | Analysis-only agents (Analyzer stage) |
| `"bypassPermissions"` | Allows all tools without confirmation | Fully autonomous agents; use with explicit tool allowlists |

### Recommendation for issue-resolver

```python
options = ClaudeAgentOptions(
    permission_mode="bypassPermissions",
    # Limit blast radius with an explicit tool allowlist
    allowed_tools=["Read", "Edit", "Bash", "Grep", "get_github_issue", "create_pull_request"],
    disallowed_tools=["WebFetch"],  # Prevent uncontrolled network access
)
```

`bypassPermissions` with an explicit `allowed_tools` list is the correct balance: the agent does not pause for confirmation, but it cannot use tools outside the declared set.

### Dynamic Permission Mode Change

`ClaudeSDKClient.set_permission_mode(mode)` can change permissions mid-session:

```python
# Start analysis in read-only mode
await client.set_permission_mode("plan")
await client.query("Analyze the issue...")
# ... collect analysis ...

# Switch to write mode for implementation
await client.set_permission_mode("acceptEdits")
await client.query("Now implement the fix...")
```

---

## 7. Error Handling Patterns When an Agent Fails Mid-Pipeline

### Error Types (from `_errors.py`)

```python
ClaudeSDKError          # Base class for all SDK errors
  CLIConnectionError    # Cannot connect to Claude Code CLI
    CLINotFoundError    # claude binary not found / not installed
  ProcessError          # CLI process exited with non-zero code
    .exit_code: int | None
    .stderr: str | None
  CLIJSONDecodeError    # CLI output is not valid JSON
    .line: str
    .original_error: Exception
```

### In-Stream Error Signals

Non-fatal errors arrive as messages in the stream:

- `AssistantMessage.error`: One of `"authentication_failed"`, `"billing_error"`, `"rate_limit"`, `"invalid_request"`, `"server_error"`, `"unknown"`
- `ResultMessage.is_error`: Boolean — `True` when the agent run ended abnormally
- `ResultMessage.stop_reason`: String reason for stopping
- `RateLimitEvent`: Emitted when rate limit status changes (check `.rate_limit_info.status == "rejected"`)
- `TaskNotificationMessage.status == "failed"`: A sub-agent task failed

### Pattern: Per-Stage Error Handling with Retry

```python
import asyncio
from claude_agent_sdk import (
    ClaudeSDKClient, AssistantMessage, ResultMessage, RateLimitEvent,
    ClaudeSDKError, ProcessError
)

MAX_RETRIES = 3

async def run_stage(client, prompt: str, stage_name: str) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            await client.query(prompt)
            result_text = ""
            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage) and msg.error:
                    raise RuntimeError(f"{stage_name} agent error: {msg.error}")
                if isinstance(msg, RateLimitEvent):
                    if msg.rate_limit_info.status == "rejected":
                        wait = 60  # Back off
                        await asyncio.sleep(wait)
                if isinstance(msg, ResultMessage):
                    if msg.is_error:
                        raise RuntimeError(f"{stage_name} failed: {msg.stop_reason}")
                    return result_text
            return result_text
        except ProcessError as e:
            if attempt == MAX_RETRIES - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
    return ""
```

### Pattern: Pipeline Abort on Critical Failure

Wrap the full pipeline in a try/except and disconnect the client in the `finally` block. `ClaudeSDKClient` used as an async context manager (`async with`) handles this automatically:

```python
async with ClaudeSDKClient(options) as client:
    try:
        analysis = await run_stage(client, analyze_prompt, "analyzer")
        fix      = await run_stage(client, fix_prompt(analysis), "bug-fixer")
        review   = await run_stage(client, review_prompt(fix), "reviewer")
        pr_url   = await run_stage(client, pr_prompt(review), "pr-creator")
    except RuntimeError as e:
        # Log failure, do not create PR
        print(f"Pipeline aborted: {e}")
        raise
# client.disconnect() called automatically by __aexit__
```

### TaskNotification Messages for Sub-Agent Monitoring

When the orchestrator spawns sub-agents via the `Task` tool, the message stream emits:

- `TaskStartedMessage` — sub-agent started (has `task_id`, `description`, `session_id`)
- `TaskProgressMessage` — periodic progress update (has `usage: TaskUsage`)
- `TaskNotificationMessage` — terminal event: `status` is `"completed"`, `"failed"`, or `"stopped"`

Use `task_id` to correlate progress/notification messages with their start event.

---

## 8. Memory / State Sharing Between Pipeline Stages

The SDK provides no shared in-process memory object between stages. State management is the application's responsibility. Available mechanisms:

### A. Python Variables (in-process, ephemeral)

Simplest approach: collect `ResultMessage.result` or `ResultMessage.structured_output` from each stage, hold in Python variables, inject into the next stage's prompt.

```python
pipeline_state = {}
# After analyzer stage:
pipeline_state["analysis"] = result_message.structured_output
# Pass to fixer:
fixer_prompt = f"Analysis: {json.dumps(pipeline_state['analysis'])}\n\nNow fix..."
```

### B. Session Resume (`resume` + `fork_session`)

The CLI persists the full conversation transcript. A resumed session has full history without any extra work:

```python
# Stage 1: create a session
options_stage1 = ClaudeAgentOptions(cwd=repo_path, ...)
async with ClaudeSDKClient(options_stage1) as c1:
    await c1.query(analyze_prompt)
    async for msg in c1.receive_response():
        if isinstance(msg, ResultMessage):
            session_id = msg.session_id

# Stage 2: resume same session — full context is available
options_stage2 = ClaudeAgentOptions(resume=session_id, cwd=repo_path, ...)
async with ClaudeSDKClient(options_stage2) as c2:
    await c2.query(fix_prompt)   # Can refer to analysis without re-injecting it
```

### C. File-Based State (for cross-process or durable pipelines)

Write stage outputs to a file in the working directory. Subsequent agents can use `Read` tool to load it. Appropriate for pipelines that may restart or run across separate processes.

### D. Session Listing for Audit

`list_sessions()`, `get_session_info(session_id)`, and `get_session_messages(session_id)` allow querying the on-disk session store after the fact. Useful for logging, replay, or debugging.

### E. File Checkpointing for Rewind

Enable `ClaudeAgentOptions(enable_file_checkpointing=True)` to allow rolling back file changes if a stage produces bad output. Use `client.rewind_files(user_message_uuid)` to restore files to their state at any prior message.

---

## Summary Recommendation for issue-resolver Pipeline

```
Orchestrator
  ClaudeSDKClient (streaming mode, bypassPermissions)
  agents dict with named AgentDefinitions
  github SDK MCP server via create_sdk_mcp_server()
  SubagentStart/Stop hooks for monitoring
  |
  +-- Analyzer (read-only: Read, Grep, get_github_issue)
  |      Output -> structured_output (json_schema)
  |
  +-- BugFixer | FeatureDev | Refactorer  (branch on analysis result)
  |      Tools: Edit, Bash, Read
  |      Mode: acceptEdits or bypassPermissions
  |
  +-- Reviewer (read-only: Read, Grep)
  |      Output -> structured review JSON
  |
  +-- PR Creator
         Tools: Bash (gh CLI), create_pull_request MCP tool
```

State flows via prompt injection using `structured_output` from each `ResultMessage`. Use `session resume` for long pipelines to avoid hitting prompt length limits.

---

## Sources

- `/home/utakata/ドキュメント/utakata-agent/.venv/lib/python3.12/site-packages/claude_agent_sdk/__init__.py`
- `/home/utakata/ドキュメント/utakata-agent/.venv/lib/python3.12/site-packages/claude_agent_sdk/types.py`
- `/home/utakata/ドキュメント/utakata-agent/.venv/lib/python3.12/site-packages/claude_agent_sdk/client.py`
- `/home/utakata/ドキュメント/utakata-agent/.venv/lib/python3.12/site-packages/claude_agent_sdk/query.py`
- `/home/utakata/ドキュメント/utakata-agent/.venv/lib/python3.12/site-packages/claude_agent_sdk/_internal/query.py`
- `/home/utakata/ドキュメント/utakata-agent/.venv/lib/python3.12/site-packages/claude_agent_sdk/_errors.py`
- `/home/utakata/ドキュメント/utakata-agent/.venv/lib/python3.12/site-packages/claude_agent_sdk/_internal/transport/subprocess_cli.py`
