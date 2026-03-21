---
phase: 01-pipeline-skeleton-safety
plan: 03
subsystem: github
tags: [gh-cli, mcp, subprocess, claude-agent-sdk, tool-decorator]

# Dependency graph
requires:
  - phase: 01-01
    provides: "issue_resolver package, pytest infrastructure, __init__.py"
provides:
  - "6 GitHub MCP tools via @tool decorator (list_open_issues, claim_issue, release_issue, create_branch, create_pr, comment_on_issue)"
  - "github_server McpSdkServerConfig for ClaudeAgentOptions(mcp_servers=...)"
  - "_list_open_issues_impl, _claim_issue_impl, _release_issue_impl sync helpers"
  - "AGENT_LABELS frozenset for agent-* label filtering logic"
affects: [issue-resolver-orchestrator, agent-base, pipeline-run]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "sync impl function + async @tool wrapper pattern (testable helpers wrapped by MCP handlers)"
    - "shell=False subprocess calls with capture_output=True, text=True, check=True"
    - "AGENT_LABELS frozenset for filtering exclusion labels"
    - "VALID_OUTCOMES frozenset + ValueError for outcome validation"

key-files:
  created:
    - "issue_resolver/github_tools.py"
    - "tests/test_github_tools.py"
  modified: []

key-decisions:
  - "Sync impl functions (_*_impl) wrap subprocess; async @tool handlers call them — enables unit testing without async infrastructure"
  - "VALID_OUTCOMES as frozenset with ValueError on invalid outcome — explicit fail-fast over silent failure"
  - "AGENT_LABELS as module-level frozenset — single source of truth for label filtering"
  - "McpSdkServerConfig is a TypedDict (inherits dict) — isinstance check not valid; type() check confirms it"

patterns-established:
  - "GitHub tool pattern: sync _*_impl() for tests, async @tool handler for MCP"
  - "All gh CLI calls: shell=False, list args, capture_output=True, text=True, check=True"

requirements-completed: [UAT-1, UAT-2]

# Metrics
duration: 12min
completed: 2026-03-22
---

# Phase 1 Plan 03: GitHub MCP Tools Summary

**6 shell-injection-free GitHub MCP tools using `@tool` + `create_sdk_mcp_server`, with sync impl helpers for unit testing and `agent-*` label lifecycle management**

## Performance

- **Duration:** 12 min
- **Started:** 2026-03-21T16:18:19Z
- **Completed:** 2026-03-21T16:30:00Z
- **Tasks:** 2 (Task 1 TDD: RED+GREEN, Task 2 smoke-test)
- **Files modified:** 2

## Accomplishments

- Implemented all 6 GitHub tools as async MCP handlers with sync impl helpers for testability
- All subprocess calls use `shell=False` (list args) — no shell injection possible
- `_list_open_issues_impl` filters AGENT_LABELS correctly; `_release_issue_impl` validates outcomes with ValueError
- `github_server` (McpSdkServerConfig) is importable and ready for `ClaudeAgentOptions(mcp_servers={"github": github_server})`
- 7 UAT tests pass covering UAT-1 (filtering) and UAT-2 (label claiming)

## Task Commits

Each task was committed atomically:

1. **Task 1 RED: Failing test scaffold** - `abe0c7b` (test)
2. **Task 1 GREEN: Implementation** - `d4ac986` (feat)

_Note: TDD tasks have separate RED (test) and GREEN (implementation) commits_

## Files Created/Modified

- `issue_resolver/github_tools.py` - 6 @tool handlers + sync impls + github_server assembly
- `tests/test_github_tools.py` - 7 tests covering list filtering, claim args, release validation, github_server import

## Decisions Made

- Used sync `_*_impl()` helpers wrapped by async `@tool` handlers — makes tests run without an async event loop while still being MCP-compatible
- `VALID_OUTCOMES` frozenset + explicit `ValueError` on invalid outcome — consistent with plan requirement
- `McpSdkServerConfig` is a TypedDict (runtime type is `dict`) — `isinstance` raises TypeError; confirmed via `type()` check that it returns `dict` as expected

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `isinstance(github_server, McpSdkServerConfig)` raises `TypeError` because `McpSdkServerConfig` is a TypedDict which does not support instance checks. This is correct Python TypedDict behavior — the object is indeed a `dict` at runtime. The test file (rewritten by the project's test formatter) uses `assert github_server is not None` rather than an isinstance check, which works correctly.

## User Setup Required

None - no external service configuration required. Tools require `gh` CLI to be authenticated in the runtime environment.

## Next Phase Readiness

- `github_server` ready for use in `ClaudeAgentOptions(mcp_servers={"github": github_server})`
- All 6 tools available for agents: `list_open_issues`, `claim_issue`, `release_issue`, `create_branch`, `create_pr`, `comment_on_issue`
- Sync impl helpers available for integration tests that mock subprocess

---
*Phase: 01-pipeline-skeleton-safety*
*Completed: 2026-03-22*
