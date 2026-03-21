# Project State

## Current Status

**Milestone:** 1 — issue-resolver
**Phase:** Ready to start Phase 1
**Last Updated:** 2026-03-22

## Completed Work

- [x] Project initialized with GSD workflow
- [x] `.planning/PROJECT.md` created
- [x] `.planning/config.json` created (supervised mode, git tracking)
- [x] Research completed (4 agents: STACK, FEATURES, ARCHITECTURE, PITFALLS)
- [x] `.planning/research/SUMMARY.md` created
- [x] `.planning/REQUIREMENTS.md` created
- [x] `.planning/ROADMAP.md` created (6 phases)

## Next Action

Run `/gsd:plan-phase 1` to create the detailed implementation plan for Phase 1.

## Key Decisions Made

1. **`ClaudeSDKClient` (not `query()`)** — AgentDefinition only works with ClaudeSDKClient
2. **`bypassPermissions` + `allowed_tools`** — Required for autonomous pipeline operation
3. **`IssueContext` as pipeline handoff** — JSON-serializable dataclass, append-only
4. **GitHub MCP Server first** — All agents depend on it; build in Phase 1
5. **Process one issue per run** — GitHub token rate limit (1,000 req/hour)
6. **Label locking** — `agent-processing` → `agent-resolved/skip/failed` lifecycle

## Architecture Decisions

- Project structure: `{workflow-name}/` directories at repo root
- First workflow: `issue-resolver/` with 7 modules
- Entry point: `main.py` dispatches to workflow `run.py`
- GitHub integration: `gh` CLI via custom `@tool` MCP server
