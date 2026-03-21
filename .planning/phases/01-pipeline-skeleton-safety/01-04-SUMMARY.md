---
phase: 01-pipeline-skeleton-safety
plan: 04
subsystem: pipeline
tags: [claude_agent_sdk, AgentBase, ClaudeSDKClient, HookMatcher, bypassPermissions, pipeline, stubs]

# Dependency graph
requires:
  - phase: 01-02
    provides: IssueContext dataclass and validate_pre_pr safety gate
  - phase: 01-03
    provides: github_server McpSdkServerConfig and _*_impl() synchronous helpers

provides:
  - AgentBase class with bypassPermissions, allowed_tools, SubagentStart/SubagentStop logging hooks
  - AnalyzerAgent stub (Phase 2 implementation target)
  - SpecialistBase, BugFixerAgent, FeatureDevAgent, RefactorerAgent stubs (Phase 3 targets)
  - ReviewerAgent stub (Phase 4 target)
  - run.py pipeline entry point callable from main.py
  - main.py updated to ClaudeSDKClient-based architecture (query() removed)
affects: [02-analyzer, 03-specialist, 04-reviewer, 05-pr-creator]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AgentBase inheritance: all pipeline agents subclass AgentBase, override allowed_tools, call _make_options()"
    - "Hook pattern: SubagentStart/SubagentStop hooks wired via HookMatcher(hooks=[callback]) in ClaudeAgentOptions"
    - "Pipeline entry: main.py -> issue_resolver.run.run() -> asyncio.run(_run_pipeline())"
    - "Stub pattern: NotImplementedError with explicit Phase N label marks future implementation targets"

key-files:
  created:
    - issue_resolver/agent_base.py
    - issue_resolver/analyzer.py
    - issue_resolver/specialist.py
    - issue_resolver/reviewer.py
    - issue_resolver/run.py
  modified:
    - main.py

key-decisions:
  - "AgentBase._make_options() provides bypassPermissions + SubagentStart/SubagentStop hooks as standard for all agents"
  - "main.py delegates entirely to issue_resolver.run.run() — no direct query() usage"
  - "Stub agents use NotImplementedError with Phase N label so future executors know exactly what to implement"

patterns-established:
  - "AgentBase inheritance: subclass AgentBase, override allowed_tools, call _make_options() for ClaudeAgentOptions"
  - "Pipeline entry point: asyncio.run() wraps async _run_pipeline() in sync run() for main.py compatibility"
  - "Stub modules: Phase N label in NotImplementedError message as documentation contract"

requirements-completed: [UAT-1, UAT-2, UAT-3, UAT-4a, UAT-4b, UAT-4c, UAT-4d]

# Metrics
duration: 2min
completed: 2026-03-21
---

# Phase 1 Plan 04: AgentBase + Pipeline Skeleton Summary

**AgentBase class with bypassPermissions and SubagentStart/SubagentStop hooks wiring all 9 issue_resolver modules into a runnable pipeline skeleton callable from main.py**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-21T16:23:59Z
- **Completed:** 2026-03-21T16:25:37Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments
- AgentBase class providing ClaudeSDKClient-based foundation for all pipeline agents with bypassPermissions and hook infrastructure
- Module skeleton with 4 new stub files (analyzer, specialist, reviewer, run) completing the 9-module issue_resolver package
- main.py updated to remove query() and route entirely through issue_resolver.run.run()
- All 23 existing tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: AgentBase and module skeleton stubs** - `f048ece` (feat)
2. **Task 2: run.py pipeline entry point and main.py update** - `7335b57` (feat)
3. **Task 3: Full test suite verification** - No commit (verification only, no file changes)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `issue_resolver/agent_base.py` - AgentBase with _make_options(), _on_subagent_start(), _on_subagent_stop()
- `issue_resolver/analyzer.py` - AnalyzerAgent stub with allowed_tools=["Read","Grep","Glob"]
- `issue_resolver/specialist.py` - SpecialistBase + BugFixerAgent + FeatureDevAgent + RefactorerAgent stubs
- `issue_resolver/reviewer.py` - ReviewerAgent stub with allowed_tools=["Read","Grep","Bash"]
- `issue_resolver/run.py` - Pipeline entry point: list/claim/release issue flow with asyncio.run()
- `main.py` - Updated from query() placeholder to issue_resolver.run.run() delegation

## Decisions Made
- HookMatcher(hooks=[callback]) API confirmed against installed SDK — `matcher` param is optional, hooks list is the primary argument
- ClaudeAgentOptions `hooks` field uses string keys matching hook type names exactly ("SubagentStart", "SubagentStop")
- run.py releases issue as "skip" when pipeline skeleton is invoked (agents not yet implemented) — prevents label lock
- main.py delegates entirely to run.py with no direct SDK imports; ClaudeSDKClient usage lives in AgentBase subclasses

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None — SDK API matched plan interfaces exactly. All imports resolved immediately.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 1 complete: all 9 module files exist and are importable, 23 tests pass, pipeline skeleton runnable
- Phase 2 (Analyzer): implement AnalyzerAgent.run() — inherits AgentBase, has IssueContext contract
- Phase 3 (Specialist): implement SpecialistBase.run() and subclasses — BugFixer, FeatureDev, Refactorer
- Phase 4 (Reviewer): implement ReviewerAgent.run() — diff audit, bandit, review_passed flag
- No blockers for Phase 2

---
*Phase: 01-pipeline-skeleton-safety*
*Completed: 2026-03-21*
