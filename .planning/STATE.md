# Project State

## Current Status

**Milestone:** 1 — issue-resolver
**Phase:** 01-pipeline-skeleton-safety (In Progress)
**Current Plan:** 01-04 of 4
**Last Updated:** 2026-03-22
**Last Session:** 2026-03-21T16:30:00Z
**Stopped At:** Completed 01-03-PLAN.md

## Completed Work

- [x] Project initialized with GSD workflow
- [x] `.planning/PROJECT.md` created
- [x] `.planning/config.json` created (supervised mode, git tracking)
- [x] Research completed (4 agents: STACK, FEATURES, ARCHITECTURE, PITFALLS)
- [x] `.planning/research/SUMMARY.md` created
- [x] `.planning/REQUIREMENTS.md` created
- [x] `.planning/ROADMAP.md` created (6 phases)
- [x] Phase 1 plans created (4 plans: 01-01 through 01-04)
- [x] **01-01-PLAN.md** — Wave 0 test scaffold: pytest + 3 failing test files + issue_resolver package
- [x] **01-03-PLAN.md** — GitHub MCP tools: 6 @tool handlers, github_server McpSdkServerConfig, shell=False subprocess, AGENT_LABELS filtering

## Next Action

Execute plan 01-04: AgentBase + ClaudeSDKClient integration (TDD)

## Key Decisions Made

1. **`ClaudeSDKClient` (not `query()`)** — AgentDefinition only works with ClaudeSDKClient
2. **`bypassPermissions` + `allowed_tools`** — Required for autonomous pipeline operation
3. **`IssueContext` as pipeline handoff** — JSON-serializable dataclass, append-only
4. **GitHub MCP Server first** — All agents depend on it; build in Phase 1
5. **Process one issue per run** — GitHub token rate limit (1,000 req/hour)
6. **Label locking** — `agent-processing` → `agent-resolved/skip/failed` lifecycle
7. **`issue_resolver/` (underscore not hyphen)** — Python cannot import hyphenated package names; directory named issue_resolver/ for importability
8. **Sync impl + async @tool wrapper pattern** — `_*_impl()` sync helpers enable unit testing without async infrastructure; async @tool handlers call them for MCP compatibility
9. **McpSdkServerConfig is TypedDict (runtime: dict)** — isinstance check raises TypeError; type() returns dict as expected; confirmed via smoke-test

## Architecture Decisions

- Project structure: `{workflow-name}/` directories at repo root
- First workflow: `issue-resolver/` with 7 modules
- Entry point: `main.py` dispatches to workflow `run.py`
- GitHub integration: `gh` CLI via custom `@tool` MCP server
