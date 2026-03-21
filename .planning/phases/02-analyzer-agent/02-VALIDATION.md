---
phase: 2
slug: analyzer-agent
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 9.0.2 |
| **Config file** | pyproject.toml (implicit — no pytest.ini) |
| **Quick run command** | `uv run pytest tests/test_analyzer.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_analyzer.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 0 | FR-2a,FR-2b,FR-2c,FR-2d,FR-2e,UAT | unit/integration | `uv run pytest tests/test_analyzer.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 1 | FR-2a | unit | `uv run pytest tests/test_analyzer.py::TestBuildPrompt -x` | ❌ W0 | ⬜ pending |
| 2-02-02 | 02 | 1 | FR-2c | unit | `uv run pytest tests/test_analyzer.py::TestIssueType -x` | ❌ W0 | ⬜ pending |
| 2-02-03 | 02 | 1 | FR-2e | unit | `uv run pytest tests/test_analyzer.py::TestComplexityScore -x` | ❌ W0 | ⬜ pending |
| 2-03-01 | 03 | 2 | FR-2b,FR-2d | unit (mock SDK) | `uv run pytest tests/test_analyzer.py::TestAnalyzerRun -x` | ❌ W0 | ⬜ pending |
| 2-04-01 | 04 | 3 | UAT-bug,UAT-affected,UAT-overlimit,UAT-readonly | integration (mock SDK) | `uv run pytest tests/test_analyzer.py::TestUAT -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_analyzer.py` — stubs covering all FR-2 and UAT requirements
  - `TestBuildPrompt` — FR-2a: Issue title/body context extraction → included in prompt
  - `TestAnalyzerRun` — FR-2b: Codebase exploration produces affected_files (mock SDK)
  - `TestIssueType` — FR-2c: Issue type judgment: label priority then LLM
  - `TestImplementationPlan` — FR-2d: Implementation plan generated (numbered steps + test cmd)
  - `TestComplexityScore` — FR-2e: Complexity score skip (ambiguous Issue → 11.0)
  - `TestUAT::test_bug_issue_type` — UAT-bug: Bug report → issue_type == "bug"
  - `TestUAT::test_affected_files_nonempty` — UAT-affected: affected_files contains related files
  - `TestUAT::test_overlimit_complexity` — UAT-overlimit: 15+ file issue → complexity_score > 8
  - `TestUAT::test_no_write_tools` — UAT-readonly: Analyzer makes no file changes

*Existing infrastructure covers all phase requirements (pytest already installed, 23 tests passing).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LLM judgment accuracy for unlabeled issues | FR-2c fallback | Requires real LLM call; mock cannot validate semantic understanding | Run with a real unlabeled issue and verify issue_type is reasonable |
| output_format passthrough via subprocess transport | FR-2b | Integration behavior of claude-agent-sdk subprocess transport at v0.1.50 | Check ResultMessage.structured_output is not None after real agent run |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
