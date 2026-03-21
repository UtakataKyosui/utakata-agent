# Architecture Patterns: Autonomous Coding Agent Pipeline

**Domain:** AI-driven GitHub Issue resolution pipeline
**Researched:** 2026-03-22
**Overall confidence:** HIGH (training data well-established for these patterns; verified against known SDK behaviors)

---

## 1. Issue Analyzer: Determining Relevant Files

### Core Strategy: Layered Signal Aggregation

The Analyzer must build a ranked list of affected files by combining multiple weak signals into a strong composite score. No single signal is reliable alone.

**Signal Priority Order (highest to lowest):**

```
1. Explicit file paths in the issue body (regex: src/foo/bar.py, ./lib/utils.ts)
2. Stack trace / error output with file:line references
3. Mentioned function/class/symbol names → resolve to files via grep
4. Mentioned module names or feature areas → resolve via directory scan
5. Git blame / recent change correlation for described behavior
6. Keyword frequency analysis against file names and docstrings
```

**Decision Tree — Analyzer File Resolution:**

```
Issue body received
       |
       v
[1] Extract explicit paths (regex scan)
       |
   Found? ──YES──> Add to candidate list (HIGH confidence)
       |
      NO
       v
[2] Extract error traces / line references
       |
   Found? ──YES──> Add to candidate list (HIGH confidence)
       |
      NO
       v
[3] Extract symbol names (function, class, method, variable)
       |
   Found? ──YES──> grep codebase for symbol → Add matches (MEDIUM confidence)
       |
      NO
       v
[4] Extract feature area keywords
       |
       v
   Map keywords → directory names / module names
   (e.g., "authentication" → auth/, login/, jwt/)
   Add matching dirs (LOW confidence, flag as uncertain)
       |
       v
[5] If still no candidates → ESCALATE (too vague for safe resolution)
```

**Implementation pattern:**

```python
class FileRelevanceAnalyzer:
    """
    Pass this prompt to the Analyzer agent. The agent uses Read/Grep tools
    to resolve symbols to file paths.
    """
    SYSTEM_PROMPT = """
    You are a codebase analyst. Given a GitHub Issue:
    1. List every file path, symbol name, and module name you can extract.
    2. Use Grep to find where each symbol is defined and used.
    3. Rank files by relevance: direct reference > symbol definition > symbol usage > module area.
    4. Return a structured JSON with: { "files": [...], "confidence": "high|medium|low", "uncertain": bool }
    5. If you cannot identify files with medium+ confidence, set uncertain=true.
    """
```

**What to pass to the Analyzer agent (tool allowlist):**

- `Read` — to read issue details
- `Grep` — to search codebase for symbols
- `Glob` — to scan directory structure
- `Bash` (read-only: `git log --oneline`, `git diff --name-only`) — to find recently changed files

Do NOT allow `Write`, `Edit`, or destructive `Bash` commands in the Analyzer stage.

---

## 2. Context Passed from Analyzer to Specialist Agents

### Minimal Context Contract (IssueContext)

The context object passed between pipeline stages must be:
- **Serializable** (JSON-safe — no live objects, no file handles)
- **Immutable from the specialist's perspective** (specialists append to it, never mutate Analyzer outputs)
- **Self-contained** (the specialist must be able to resume from context alone)

```python
# Canonical context schema — pass as JSON between agents
IssueContext = {
    # Identity
    "issue_number": int,
    "issue_url": str,
    "issue_title": str,
    "issue_body": str,
    "issue_labels": list[str],

    # Analyzer outputs
    "issue_type": "bug" | "feature" | "refactor" | "ambiguous",
    "affected_files": [
        {
            "path": str,           # relative to repo root
            "confidence": "high" | "medium" | "low",
            "reason": str          # why this file was selected
        }
    ],
    "symbols_mentioned": list[str],  # function/class names from issue
    "analyzer_confidence": "high" | "medium" | "low",
    "analyzer_notes": str,           # free-text reasoning from Analyzer

    # Routing decision
    "routed_to": "bug_fixer" | "feature_dev" | "refactorer",
    "routing_reason": str,

    # Populated by specialist
    "implementation_notes": str,
    "files_modified": list[str],
    "tests_run": bool,
    "tests_passed": bool | None,
    "test_output": str,

    # Populated by Reviewer
    "review_passed": bool | None,
    "review_notes": str,

    # Pipeline control
    "status": "pending" | "in_progress" | "done" | "skipped" | "failed",
    "skip_reason": str | None,       # populated if status == "skipped"
    "pipeline_errors": list[str]     # any non-fatal errors encountered
}
```

**What each specialist NEEDS from the Analyzer (minimum viable):**

| Agent | Required fields | Why |
|-------|----------------|-----|
| BugFixer | `issue_body`, `affected_files` (HIGH conf only), `symbols_mentioned` | Needs to read the broken code |
| FeatureDev | `issue_body`, `affected_files`, `analyzer_notes`, `issue_labels` | Needs scope + neighbor context |
| Refactorer | `affected_files`, `symbols_mentioned`, `analyzer_notes` | Needs to know what to touch |
| Reviewer | `files_modified`, `issue_body`, `implementation_notes`, `issue_type` | Needs diff context + intent |

---

## 3. Handling Issues Too Complex or Ambiguous for AI

### Complexity Detection Heuristics

The Analyzer must evaluate complexity before routing. Apply these checks:

**Structural signals (measurable):**

```
SKIP if any of the following:
- affected_files count > 15                     (too broad a blast radius)
- affected_files all have confidence == "low"    (no reliable anchors)
- issue_body word count < 30                     (too vague)
- issue_body contains "breaking change" AND affected_files > 5
- issue_labels contains "needs-discussion" or "rfc" or "design"
- issue references cross-repo dependencies
- issue mentions database migrations
- issue mentions security/auth changes
```

**Semantic signals (LLM judgment):**

```
Ask the Analyzer agent:
"On a scale of 1-5, how confident are you that:
  (a) you fully understand what the desired outcome is?
  (b) the change is self-contained to this repository?
  (c) the change can be safely made without breaking unrelated features?

If any score is < 3, set uncertain=true."
```

**Decision Tree — Complexity Gate:**

```
Analyzer outputs IssueContext
         |
         v
[Gate 1] analyzer_confidence == "low"?
         YES → SKIP, comment "Could not identify affected code"
         |
        NO
         v
[Gate 2] len(affected_files) > 15?
         YES → SKIP, comment "Too broad — affects too many files"
         |
        NO
         v
[Gate 3] issue_type == "ambiguous"?
         YES → SKIP, comment "Issue intent unclear — needs clarification"
         |
        NO
         v
[Gate 4] issue mentions schema change / migration / security?
         YES → SKIP, comment "Requires human judgment — security/data concern"
         |
        NO
         v
PROCEED to specialist agent
```

**Skip Comment Template:**

```markdown
<!-- utakata-agent automated comment -->
Hi! I attempted to analyze this issue but decided not to proceed automatically.

**Reason:** {skip_reason}

**What I found:**
- Issue type: {issue_type}
- Potentially affected files: {file_list}
- Confidence: {analyzer_confidence}

**Next steps:** This issue needs human review before automated processing can continue.
A human should clarify the scope or manually implement the changes.

_— utakata-agent_
```

---

## 4. State Management Between Pipeline Stages

### Minimal State Principle

Pass only what the NEXT stage needs, not everything. Avoid bloating context with raw file contents — agents re-read files with tools.

**What NOT to pass between stages:**

```
- Full file contents (agents read them with Read tool when needed)
- Full git diff (Reviewer re-runs git diff with Bash tool)
- Entire issue thread (pass issue_number; agents fetch detail if needed)
- Tool execution logs from previous stages
- Intermediate reasoning steps
```

**State machine — pipeline transitions:**

```
[START]
  → IssueContext created (issue_number, issue_body, issue_labels)

[AFTER ANALYZER]
  → Adds: issue_type, affected_files, symbols_mentioned,
          analyzer_confidence, analyzer_notes, routed_to

[AFTER SPECIALIST]
  → Adds: implementation_notes, files_modified,
          tests_run, tests_passed, test_output

[AFTER REVIEWER]
  → Adds: review_passed, review_notes

[AFTER PR_CREATOR]
  → Adds: pr_url, branch_name, status = "done"
```

**Persistence strategy:**

Store the IssueContext as a JSON file during pipeline execution. This enables:
- Resume after crash
- Audit trail
- Debugging failed runs

```
.pipeline_state/
  issue-{number}-{timestamp}.json   ← one file per issue per run
```

**Between-stage handoff pattern:**

```python
# Each stage reads its input, does work, writes augmented output
def run_stage(stage_name: str, context: dict) -> dict:
    context["status"] = "in_progress"
    context["current_stage"] = stage_name
    # ... do work ...
    context["status"] = "pending"  # ready for next stage
    save_state(context)            # persist before next stage
    return context
```

---

## 5. Safeguard Patterns — Preventing Harmful Changes

### Defense-in-Depth Model

Apply safeguards at three layers: tool allowlist, blast radius limits, and post-hoc review.

**Layer 1: Tool Allowlist Per Stage**

```python
STAGE_TOOLS = {
    "analyzer":    ["Read", "Grep", "Glob", "Bash:readonly"],
    "bug_fixer":   ["Read", "Grep", "Glob", "Edit", "Bash:test_only"],
    "feature_dev": ["Read", "Grep", "Glob", "Write", "Edit", "Bash:test_only"],
    "refactorer":  ["Read", "Grep", "Glob", "Edit", "Bash:test_only"],
    "reviewer":    ["Read", "Grep", "Glob", "Bash:readonly"],
    "pr_creator":  ["Bash:git_only"]
}
```

"Bash:readonly" means the Bash tool is permitted but the system prompt explicitly forbids
write operations. The SDK's `permissionMode` should be set to `acceptEdits` only for
specialist stages.

**Layer 2: File Modification Boundaries**

The specialist agent's system prompt must include explicit scope limits:

```
BOUNDARY RULES (in specialist system prompt):
1. Only modify files listed in context["affected_files"] with confidence >= "medium"
2. Do NOT modify: .github/, CI config files, package.json/pyproject.toml (deps),
   Makefile, Dockerfile, migration files, .env files, security-related modules
3. Do NOT add new package dependencies without explicit instruction in the issue
4. New files may only be created in directories that already exist in the codebase
5. Maximum files modifiable per run: 10
```

**Layer 3: Pre-PR Validation Gate**

Before the PR creator runs, validate:

```python
def pre_pr_validation(context: dict) -> tuple[bool, str]:
    """All checks must pass or PR is blocked."""

    # 1. Tests must have been run
    if not context["tests_run"]:
        return False, "Tests were not executed"

    # 2. Tests must pass
    if context["tests_passed"] is False:
        return False, f"Tests failed: {context['test_output'][:500]}"

    # 3. Review must pass
    if not context["review_passed"]:
        return False, f"Review failed: {context['review_notes']}"

    # 4. Files modified must be subset of files analyzed
    analyzed = {f["path"] for f in context["affected_files"]}
    modified = set(context["files_modified"])
    surprise_files = modified - analyzed
    if surprise_files:
        return False, f"Agent modified unexpected files: {surprise_files}"

    # 5. No protected files touched
    PROTECTED = {".github/", "migrations/", ".env", "secrets"}
    for f in context["files_modified"]:
        if any(p in f for p in PROTECTED):
            return False, f"Protected file modified: {f}"

    return True, "OK"
```

**Layer 4: PR Size Limits**

```python
# In pr_creator.py — check diff size before creating PR
MAX_LINES_CHANGED = 500
MAX_FILES_CHANGED = 10

diff_stats = run("git diff --stat HEAD main")
if lines_changed > MAX_LINES_CHANGED or files_changed > MAX_FILES_CHANGED:
    skip_with_comment("Change too large for automated PR — needs human review")
```

---

## 6. Branch Naming Conventions for AI-Generated PRs

### Convention: Namespaced by agent, typed by issue, scoped to issue number

```
ai/{type}/{issue-number}/{slug}

Examples:
  ai/bug/123/fix-null-pointer-in-auth
  ai/feature/456/add-user-export-endpoint
  ai/refactor/789/extract-payment-service
```

**Rules:**
- Always prefix with `ai/` — makes filtering easy (`git branch -r | grep ai/`)
- Type reflects `issue_type` from IssueContext (`bug`, `feature`, `refactor`)
- Issue number enables direct cross-reference
- Slug is max 40 chars, lowercase, hyphens only, derived from issue title

**Slug generation:**

```python
import re

def make_branch_slug(issue_title: str) -> str:
    slug = issue_title.lower()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)   # keep alphanumeric + hyphens
    slug = re.sub(r"\s+", "-", slug.strip())     # spaces to hyphens
    slug = re.sub(r"-+", "-", slug)              # collapse double hyphens
    return slug[:40].rstrip("-")

# "Fix: NullPointerException in AuthService.validate()"
# → "fix-nullpointerexception-in-authservice"
```

**Branch lifecycle:**
- Created fresh per pipeline run (never reuse across runs)
- If branch already exists (prior failed run): delete and recreate, or append `-v2`
- Never push directly to `main` or `master`

---

## 7. PR Description Best Practices for AI-Generated PRs

### Core Principle: Maximum Transparency, Zero Ambiguity

Humans reviewing AI PRs need to know: what was changed, why, and how to verify it.

**PR Description Template:**

```markdown
## Summary

<!-- One sentence: what this PR does -->
{implementation_notes}

Closes #{issue_number}

---

## Issue Analysis

**Issue type:** {issue_type}
**Analyzer confidence:** {analyzer_confidence}

**Files identified as relevant:**
{affected_files_table}

---

## Changes Made

**Files modified:**
{files_modified_list}

**Approach:**
{implementation_reasoning}

---

## Testing

- Tests run: {tests_run}
- Tests passed: {tests_passed}
- Test command used: `{test_command}`

<details>
<summary>Test output</summary>

```
{test_output}
```

</details>

---

## Review Notes

{review_notes}

---

## Reviewer Checklist

- [ ] The change matches the intent of the linked issue
- [ ] No unintended files were modified
- [ ] Tests adequately cover the change
- [ ] The approach is appropriate (not over-engineered)
- [ ] No security implications overlooked

---

<!-- Generated by utakata-agent | Issue #{issue_number} | Run: {timestamp} -->
```

**PR Title format:**

```
[AI] {verb}: {concise description} (#{issue_number})

Examples:
  [AI] Fix: null pointer in AuthService.validate() (#123)
  [AI] Add: user data export endpoint (#456)
  [AI] Refactor: extract PaymentService from OrderController (#789)
```

**Labels to apply programmatically:**

```
ai-generated        ← always apply
needs-human-review  ← always apply
bug-fix / feature / refactor  ← based on issue_type
```

---

## 8. Detecting and Running Tests Appropriately

### Test Detection: Language-Agnostic Scan

The agent must detect the test setup before running tests. Do not hardcode `pytest` or `npm test`.

**Detection Decision Tree:**

```
Scan repo root and common subdirs
         |
         v
[Python] pyproject.toml with [tool.pytest] or pytest.ini?
         YES → runner = "pytest", confidence = HIGH
         |
[Python] setup.cfg with [tool:pytest]?
         YES → runner = "pytest", confidence = HIGH
         |
[Python] tests/ or test_*.py files exist?
         YES → runner = "pytest", confidence = MEDIUM
         |
[Node]   package.json with "scripts.test"?
         YES → runner = "npm test" (or yarn/pnpm by lockfile), confidence = HIGH
         |
[Node]   jest.config.js / vitest.config.ts?
         YES → runner = "npx jest" / "npx vitest run", confidence = HIGH
         |
[Rust]   Cargo.toml exists?
         YES → runner = "cargo test", confidence = HIGH
         |
[Go]     go.mod exists?
         YES → runner = "go test ./...", confidence = HIGH
         |
[Ruby]   Gemfile with rspec / minitest?
         YES → runner = "bundle exec rspec", confidence = HIGH
         |
No test files found?
         → tests_run = false, tests_passed = null
         → Note in PR: "No test suite detected"
```

**Implementation:**

```python
def detect_test_runner(repo_root: str) -> dict:
    """Returns { "command": str, "confidence": str } or None."""

    checks = [
        # Python — pytest
        (["pytest.ini", "pyproject.toml", "setup.cfg"], "pytest", detect_pytest),
        # Node
        (["package.json"], "npm test", detect_node_test),
        # Rust
        (["Cargo.toml"], "cargo test", lambda _: True),
        # Go
        (["go.mod"], "go test ./...", lambda _: True),
        # Ruby
        (["Gemfile"], "bundle exec rspec", detect_rspec),
    ]

    for marker_files, command, verifier in checks:
        if any(os.path.exists(os.path.join(repo_root, f)) for f in marker_files):
            if verifier(repo_root):
                return {"command": command, "confidence": "high"}

    return None  # no test suite detected
```

**Test execution rules:**

```
1. Run tests BEFORE implementation to get a baseline (capture failures that pre-exist)
2. Run tests AFTER implementation
3. Compare: new failures = agent's fault; pre-existing failures = note in PR
4. Timeout: 5 minutes max — kill and mark as inconclusive if exceeded
5. Capture stdout + stderr (truncate to 2000 chars for context storage)
6. Never run with --force, --no-verify, or test-disabling flags
7. If test runner not found: skip test step, note in PR, do NOT block PR creation
   (because some repos have no tests — that's legitimate)
```

**Baseline comparison pattern:**

```python
def run_tests_with_baseline(test_command: str) -> dict:
    # Run on main branch before checkout to feature branch
    baseline = run_tests(test_command, branch="main")

    # Checkout feature branch and run again
    checkout_feature_branch()
    after = run_tests(test_command, branch="feature")

    return {
        "baseline_passed": baseline["passed"],
        "baseline_failures": baseline["failures"],
        "after_passed": after["passed"],
        "after_failures": after["failures"],
        "regressions": after["failures"] - baseline["failures"],  # set difference
        "tests_introduced_failures": len(regressions) > 0
    }
```

---

## Component Boundaries Summary

| Component | Responsibility | Tools Allowed | Can Modify Files? |
|-----------|---------------|---------------|-------------------|
| Orchestrator | Fetch issues, filter, dispatch | Bash (gh CLI) | No |
| Analyzer | Classify issue, find files, gate complexity | Read, Grep, Glob, Bash:readonly | No |
| BugFixer | Fix broken behavior | Read, Grep, Edit, Bash:test | Only affected_files |
| FeatureDev | Implement new functionality | Read, Grep, Write, Edit, Bash:test | Only affected_files + new files |
| Refactorer | Improve structure without behavior change | Read, Grep, Edit, Bash:test | Only affected_files |
| Reviewer | Validate correctness + safety | Read, Grep, Bash:readonly | No |
| PR Creator | Branch, commit, PR | Bash:git_only | No (git only) |

---

## Data Flow Diagram

```
GitHub API
    |
    v
Orchestrator
    | → issues[] (list of open issues to process)
    |
    v
Analyzer (per issue)
    | → IssueContext { issue_type, affected_files, routing, confidence }
    |
    +--[confidence=low / type=ambiguous]--> SKIP → post comment on issue
    |
    v
Router
    |--[bug]-------> BugFixer
    |--[feature]---> FeatureDev
    +--[refactor]--> Refactorer
                          |
                          v
                     IssueContext { +implementation_notes, +files_modified, +tests_* }
                          |
                          v
                     [tests_passed=false] --> ABORT → post failure comment
                          |
                          v
                       Reviewer
                          |
                          v
                     [review_passed=false] --> ABORT → post review failure comment
                          |
                          v
                      PR Creator
                          |
                          v
                     [pre_pr_validation fails] --> ABORT
                          |
                          v
                       PR Created → post PR link on issue
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Passing Full File Contents in Context
**What goes wrong:** Context object bloats to megabytes; token limit errors in LLM calls.
**Instead:** Pass file paths. Each agent reads files fresh with the Read tool when needed.

### Anti-Pattern 2: Agents Modifying Each Other's Outputs
**What goes wrong:** Reviewer "fixes" code instead of reporting; breaks audit trail.
**Instead:** Each stage is append-only. Reviewer adds `review_notes` and `review_passed`; never touches `files_modified`.

### Anti-Pattern 3: Single-Stage Omniscient Agent
**What goes wrong:** One agent that does analyze + implement + review has no checks on itself.
**Instead:** Separate agents with separate system prompts and separate tool allowlists.

### Anti-Pattern 4: Optimistic Test Skipping
**What goes wrong:** "No tests found" silently becomes "tests passed = true"; broken PRs merge.
**Instead:** Distinguish `tests_run=false` (no test suite) from `tests_passed=false` (suite failed). Never coerce to true.

### Anti-Pattern 5: Branch Reuse Across Runs
**What goes wrong:** Stale commits from a prior run contaminate a new attempt.
**Instead:** Always delete and recreate the branch, or suffix with run timestamp.

### Anti-Pattern 6: Unlimited Blast Radius
**What goes wrong:** Agent rewrites 50 files "to be consistent"; unreviewed mass change merges.
**Instead:** Hard cap on files_modified (10 max). Abort and comment if exceeded.

---

## Sources

This document is based on:
- Training knowledge of autonomous agent patterns (Claude SDK, LangChain, AutoGPT architectures)
- GitHub Actions integration patterns
- Software engineering principles for bounded change sets
- Confidence: HIGH for structural patterns; MEDIUM for specific SDK behaviors (verify against claude-agent-sdk changelog)
