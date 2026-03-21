---
phase: 01-pipeline-skeleton-safety
plan: 02
subsystem: pipeline
tags: [dataclass, json, validation, subprocess, bandit, tdd]

# Dependency graph
requires:
  - phase: 01-pipeline-skeleton-safety/01-01
    provides: test scaffold with failing tests for IssueContext and validate_pre_pr

provides:
  - IssueContext dataclass with to_json/from_json serialization
  - validate_pre_pr() gate function with 4 safety checks
  - ValidationError exception for pre-PR failure reporting

affects:
  - 01-03 (github_tools — uses IssueContext as pipeline handoff)
  - 01-04 (AgentBase — uses IssueContext for agent context passing)
  - All future phases using pipeline handoff

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "@dataclass with field(default_factory=list) for mutable defaults"
    - "dataclasses.asdict() + json.dumps() for serialization"
    - "subprocess.run(list_args, capture_output=True, shell=False) for CLI calls"
    - "Module-level compiled regex constants for pattern matching"

key-files:
  created:
    - issue_resolver/context.py
    - issue_resolver/validation.py
  modified: []

key-decisions:
  - "Used dataclasses.field(default_factory=list) for affected_files, changes_made, security_issues to prevent shared mutable default bug"
  - "review_passed uses Optional[bool] = None to distinguish not-yet-reviewed (None) from rejected (False)"
  - "validate_pre_pr checks 4 conditions in strict order: scope -> test modification -> bandit -> token budget"
  - "Custom ValidationError(Exception) with docstring 'Pre-PR validation failure. Message is posted as Issue comment.'"
  - "Test pattern matching uses both os.path.basename and the full path to catch tests/test_foo.py patterns"
  - "from __future__ import annotations used to allow forward references in type hints"

patterns-established:
  - "Write-zone comments: each field group annotated with which agent owns it"
  - "validate_pre_pr signature: (ctx: IssueContext, token_count: int = 0) -> None"
  - "ValidationError messages are human-readable for GitHub Issue comment posting"

requirements-completed: [UAT-3, UAT-4a, UAT-4b, UAT-4c, UAT-4d]

# Metrics
duration: 15min
completed: 2026-03-22
---

# Phase 1 Plan 2: IssueContext Dataclass and Pre-PR Safety Gate Summary

**IssueContext flat dataclass with JSON roundtrip serialization and validate_pre_pr() 4-condition safety gate using TDD**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-21T16:18:15Z
- **Completed:** 2026-03-21T16:33:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- IssueContext dataclass with 3 required metadata fields and 4 agent write zones, fully serializable via to_json/from_json
- validate_pre_pr() enforcing 4 hard-abort conditions: out-of-scope files, existing test modification, bandit security scan, token budget
- 16 tests passing across test_context.py (8) and test_validation.py (8), covering all UAT-3, UAT-4a/b/c/d requirements

## Task Commits

Each task was committed atomically:

1. **Task 1: IssueContext dataclass (TDD GREEN)** - `c18d662` (feat)
2. **Task 2: validate_pre_pr gate function (TDD GREEN)** - `e5d690f` (feat)

_Note: TDD tasks - RED phase was the pre-existing scaffold from plan 01-01._

## Files Created/Modified
- `issue_resolver/context.py` - IssueContext @dataclass with to_json/from_json, 4 write-zone sections, Optional[bool] review_passed
- `issue_resolver/validation.py` - ValidationError exception + validate_pre_pr(ctx, token_count=0) with 4 ordered safety checks

## Decisions Made
- Used `dataclasses.field(default_factory=list)` for all list fields to prevent the Python mutable default anti-pattern
- `review_passed: Optional[bool] = None` — None means "not yet reviewed" which the Orchestrator treats as abort; False means explicitly rejected
- Implemented test pattern detection using both full path (`tests/test_foo.py` via `^tests/` pattern) and basename matching for files not under tests/
- `ValidationError` docstring explicitly states the message is intended for GitHub Issue comment posting, documenting the downstream contract

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- IssueContext is fully implemented and importable as `from issue_resolver.context import IssueContext`
- validate_pre_pr is fully implemented and importable as `from issue_resolver.validation import validate_pre_pr, ValidationError`
- Plan 01-03 (github_tools) can now import IssueContext for its claim/release operations
- Plan 01-04 (AgentBase) can use IssueContext as the pipeline handoff object

---
*Phase: 01-pipeline-skeleton-safety*
*Completed: 2026-03-22*
