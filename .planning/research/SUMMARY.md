# Project Research Summary

**Project:** utakata-agent — AI Agent workflow collection (first workflow: issue-resolver)
**Domain:** Autonomous coding agent pipeline — GitHub Issues to PRs
**Researched:** 2026-03-22
**Confidence:** HIGH (stack from primary source; features/architecture from stable documented APIs)

## Executive Summary

The issue-resolver workflow is a fully autonomous pipeline that watches a GitHub repository for open issues, processes one per cron run, and submits a PR if the fix meets all quality gates. The canonical architecture is a sequential multi-agent pipeline: Analyzer → Specialist (BugFixer / FeatureDev / Refactorer) → Reviewer → PR Creator. Each stage is a separate named `AgentDefinition` inside a single `ClaudeSDKClient` session, which is the only SDK mode that supports multi-agent definitions and bidirectional communication. The inter-stage handoff object is `IssueContext` — a JSON-serializable dict that grows monotonically as each stage appends its outputs; stages never overwrite prior outputs.

The most important design constraint is autonomous operation combined with strict blast-radius control. `bypassPermissions` + an explicit `allowed_tools` list is the correct SDK permission model: the agent runs without human interrupts, but the tool surface is narrowly bounded. Write access is gated by the Analyzer's `affected_files` allowlist — the pre-PR validation check asserts that every modified file was explicitly predicted by the Analyzer. This allowlist is the single most important safeguard in the entire pipeline.

The hardest operational risks are runaway costs, prompt injection via malicious issue bodies, and branch/label pollution from failed or repeated runs. All three are mitigated through concrete mechanisms that must be built in Phase 1, not retrofitted: a token budget ceiling (150K tokens per run), issue content wrapped in `<issue_content>` delimiters with explicit untrusted-input instructions, label-based locking with stale-lock recovery, and four hard abort conditions before any PR is created (security scan failure, test modification detected, token budget exceeded, complexity threshold breached).

---

## Key Decisions

These decisions emerged from cross-cutting research and must not be revisited without cause.

| Decision | Rationale | Source |
|----------|-----------|--------|
| Use `ClaudeSDKClient`, NOT `query()` | `agents` dict is only transmitted in the streaming-mode `initialize` handshake; `query()` silently ignores it | STACK.md §2 |
| `bypassPermissions` + `allowed_tools` | Only combination that enables autonomous operation without blocking prompts while bounding blast radius | STACK.md §6 |
| `IssueContext` as inter-stage handoff | JSON-serializable, append-only, self-contained; enables crash recovery and audit trail | ARCHITECTURE.md §2, §4 |
| Analyzer-produced file allowlist gates all write permissions | Prevents "while I'm here" scope creep; enforced in pre-PR validation | PITFALLS.md §1, ARCHITECTURE.md §5 |
| Label lifecycle for GitHub coordination | `agent-processing → agent-resolved / agent-skip / agent-failed` prevents duplicate processing and stale locks | FEATURES.md §5, §7 |
| 4 hard abort conditions before PR | Security scan, test modification detected, token budget exceeded, complexity threshold — no partial PRs | PITFALLS.md §2, §3, §4, §6 |
| Process one issue per cron run | GITHUB_TOKEN in Actions is throttled to 1,000 req/hour; one-issue-per-run bounds API usage safely | FEATURES.md §6 |

---

## Key Findings

### Recommended Stack

The SDK is `claude-agent-sdk 0.1.50`, inspected directly from the installed package. `ClaudeSDKClient` is the correct entry point for all multi-agent work — `AgentDefinition` instances in `ClaudeAgentOptions.agents` are serialized and transmitted only during the streaming-mode `initialize` handshake, which `ClaudeSDKClient` always performs. Custom GitHub tools are built with `@tool` + `create_sdk_mcp_server()`, which runs in-process (no subprocess overhead). State flows between stages via structured prompt injection using `ResultMessage.structured_output` from `ClaudeAgentOptions(output_format={"type": "json_schema", ...})`.

**Core technologies:**
- `ClaudeSDKClient` — multi-agent session host — only mode supporting `agents` dict and hooks
- `AgentDefinition` — per-stage agent configuration — `model: "inherit"` for all stages to respect caller's model
- `create_sdk_mcp_server()` + `@tool` — in-process GitHub MCP server — avoids subprocess overhead
- `bypassPermissions` + `allowed_tools` — permission model — autonomous operation with bounded surface
- `SubagentStart` / `SubagentStop` hooks — observability — `agent_id` is the only reliable parallel-attribution key
- `output_format: json_schema` — structured inter-stage output — parsed via `ResultMessage.structured_output`
- GitHub Actions cron + `concurrency.group` — scheduling + serialization — prevents race conditions
- `gh` CLI + `GH_TOKEN` env var — GitHub operations — all issue/PR/label operations from agent subprocess

### Expected Features

**Must have (table stakes):**
- Cron-triggered execution with `workflow_dispatch` for manual testing
- `permissions: {contents: write, issues: write, pull-requests: write}` at job level
- Git identity configuration (`github-actions[bot]@users.noreply.github.com`)
- Label-based issue locking: claim before work, release after (success, skip, or failure)
- Single-issue-per-run processing (rate limit constraint)
- Branch-per-issue naming (`ai/{type}/issue-{number}/{slug}`)
- PR creation with `Closes #N` body and `[AI]` title prefix
- Concurrency control (`cancel-in-progress: false`) to queue, not cancel

**Should have (differentiators):**
- Stale lock recovery: issues stuck in `agent-processing` > 2 hours auto-transition to `agent-failed`
- Rate limit preflight: abort run if GitHub API remaining < 100 requests
- Draft PR workflow: create as draft, mark ready only after all gates pass
- Token budget tracking: abort and label `agent-skip` if cumulative usage exceeds 150K tokens
- Baseline test comparison: pre/post test run to isolate agent-introduced regressions
- `agent-failure-report.md` artifact uploaded on pipeline abort

**Defer to v2+:**
- GraphQL bulk fetch (REST is sufficient at low volume)
- Auto-merge on approval (requires higher trust in pipeline)
- Multi-issue parallel processing (rate limit architecture change required)
- Mutation testing on generated code

**Anti-features (never implement):**
- Auto-merge without human review
- `git push --force` anywhere in the pipeline
- Processing all open issues in one run
- Silently swallowing exceptions while leaving labels set to `agent-processing`

### Architecture Principles

The pipeline is a linear DAG of named agents communicating through an append-only `IssueContext` object. The Orchestrator is not an agent — it is plain Python that fetches issues, filters by label, selects one, and drives the `ClaudeSDKClient` session. Each subsequent stage is a `ClaudeSDKClient` invocation (or session resume) whose system prompt includes only the fields of `IssueContext` it needs. No stage reads raw file contents into the handoff object; file paths are passed and agents re-read files with the `Read` tool.

**Major components and responsibilities:**

| Component | Responsibility | Can Modify Files? | Tool Budget |
|-----------|---------------|-------------------|-------------|
| Orchestrator | Fetch/filter issues, manage labels, drive pipeline | No | `Bash` (gh CLI only) |
| Analyzer | Classify issue, build `affected_files` allowlist, gate complexity | No | `Read`, `Grep`, `Glob`, `Bash:readonly` |
| BugFixer / FeatureDev / Refactorer | Implement change within allowlist boundaries | Only `affected_files` | `Read`, `Grep`, `Edit`, `Bash:test` |
| Reviewer | Validate correctness, security, test coverage, scope | No | `Read`, `Grep`, `Bash:readonly` |
| PR Creator | Branch, commit, push, create PR | No (git only) | `Bash:git_only` |

**Data flow:**
```
GitHub API → Orchestrator → Analyzer → [Router] → Specialist → Reviewer → PR Creator
                                           |
                              SKIP on: low confidence, >15 files,
                              ambiguous intent, security/migration scope
```

**State persistence:**
`IssueContext` is written to `.pipeline_state/issue-{number}-{timestamp}.json` after every stage. This enables crash recovery, audit trail, and debugging without re-running from scratch.

### Critical Pitfalls to Avoid

1. **Unbounded file scope** — The Analyzer must produce an explicit `affected_files` allowlist. The pre-PR validation gate must reject the entire run if any modified file is not in that list. This is the single most important safeguard. See ARCHITECTURE.md §5, PITFALLS.md §1.

2. **Security-sensitive code generation** — The Reviewer stage must run a dedicated security pass (hardcoded secrets, disabled TLS, `eval()` on external input, SQL concatenation). Run `bandit` (Python) or equivalent as a blocking static analysis step before PR Creator. See PITFALLS.md §2.

3. **Test modification to force passing** — Pre-existing tests are immutable. The Reviewer must diff test files before/after and hard-fail the pipeline if any existing assertion is removed or weakened. Agents write code that satisfies tests; they never touch the tests to satisfy code. See PITFALLS.md §3, §8.

4. **Runaway API costs and infinite loops** — Set `timeout-minutes: 30` on the GitHub Actions job. Track cumulative tokens across all stages and abort at 150K. Cap retry iterations at 2 per stage. The estimated per-issue token range is 37K–135K; the 150K ceiling is the documented safe hard limit. See PITFALLS.md §4.

5. **Prompt injection via issue body** — Issue title and body are untrusted user input. Wrap in `<issue_content>...</issue_content>` delimiters in every agent prompt with an explicit instruction that content inside those tags must not be treated as instructions. Never log `GITHUB_TOKEN` or `ANTHROPIC_API_KEY` values. See PITFALLS.md §10.

---

## Implications for Roadmap

### Phase 1: Pipeline Skeleton and Safety Infrastructure

**Rationale:** The label lifecycle, permission model, and abort gates must exist before any agent can run. Building agents first without safety infrastructure produces a pipeline that works locally but is dangerous in production. All subsequent phases depend on these foundations.

**Delivers:** Working cron workflow, label-based locking with stale recovery, `ClaudeSDKClient` session scaffold, `IssueContext` schema, pre-PR validation gate, token budget tracking.

**Addresses features:** Cron workflow YAML, git identity, concurrency control, label lifecycle (`agent-processing → resolved/skip/failed`), single-issue-per-run selection.

**Avoids pitfalls:** Branch/PR pollution (Pitfall 5), runaway costs (Pitfall 4), infinite loops (Pitfall 4).

**Research flag:** Standard patterns — no additional research needed. GitHub Actions YAML structure and `ClaudeSDKClient` session setup are fully documented in STACK.md and FEATURES.md.

### Phase 2: Analyzer Agent

**Rationale:** The `affected_files` allowlist produced by the Analyzer is the input gate for all write operations. Nothing that modifies files can be built until the Analyzer exists and produces a validated, structured allowlist.

**Delivers:** Analyzer `AgentDefinition`, layered file-relevance scoring, complexity gates (4 skip conditions), `IssueContext` population through `analyzer_confidence`, `affected_files`, `issue_type`, `routed_to`.

**Addresses features:** Issue classification (bug/feature/refactor/ambiguous), skip comment template, rate limit preflight check.

**Avoids pitfalls:** Unbounded file scope (Pitfall 1), complexity threshold (Pitfall 6), context window poisoning (Pitfall 9).

**Research flag:** Standard patterns — ARCHITECTURE.md §1 provides the complete decision tree and signal priority order. No additional research needed.

### Phase 3: Specialist Agents (BugFixer, FeatureDev, Refactorer)

**Rationale:** With the Analyzer's allowlist in place, specialist agents can be scoped correctly at construction time. All three share the same tool allowlist and boundary rules; they differ only in system prompt framing.

**Delivers:** Three `AgentDefinition` implementations, test detection logic (language-agnostic), baseline+post test execution, `IssueContext` fields `files_modified`, `tests_run`, `tests_passed`, `test_output`.

**Addresses features:** Branch-per-issue creation, test runner detection (pytest/cargo/npm/go), baseline comparison to isolate regressions.

**Avoids pitfalls:** Regression introduction (Pitfall 3), test failure recovery spiral (Pitfall 8), language/framework assumptions (Pitfall 13).

**Research flag:** Test detection logic in ARCHITECTURE.md §8 is comprehensive. Language detection for Rust is well-documented (`Cargo.toml` → `cargo test`). No additional research needed.

### Phase 4: Reviewer Agent and Pre-PR Validation

**Rationale:** The Reviewer is the last safety layer before a PR is created. It must be built and hardened before the PR Creator, not after. The Reviewer's `review_passed: true` flag is the required precondition for PR creation.

**Delivers:** Reviewer `AgentDefinition` with mandatory security pass, test modification detection (diff of test files), scope audit (all `files_modified` within `affected_files`), structured `review_passed` + `review_notes` output. Python `pre_pr_validation()` function as the hard gate.

**Addresses features:** Security scan (bandit / pattern regex), protected file check, PR size limit (500 lines / 10 files max).

**Avoids pitfalls:** Security-sensitive code generation (Pitfall 2), test modification (Pitfall 3), unbounded file scope (Pitfall 1), rubber-stamp reviewer (Pitfall — must raise at least one concern).

**Research flag:** The Reviewer "must find at least one concern" instruction (PITFALLS.md phase warnings table) is a non-obvious requirement — do not skip it.

### Phase 5: PR Creator and Observability

**Rationale:** PR creation is the final, irreversible external action. It should be the last piece built, after all gates are proven in isolation.

**Delivers:** PR Creator `AgentDefinition`, structured PR description template (populated per-field, not free-form), `[AI]` title prefix, `ai-generated` + `needs-human-review` labels, `agent-failure-report.md` artifact upload on abort, `SubagentStart/Stop` hook logging for run observability.

**Addresses features:** Draft PR workflow (`--draft` + `gh pr ready`), idempotency check (existing PR for same issue), commit message template with run URL, `agent-resolved` label on success.

**Avoids pitfalls:** Branch/PR pollution (Pitfall 5), misleading PR descriptions (Pitfall 7), non-deterministic behavior (Pitfall 11), commit message quality (Pitfall 12).

**Research flag:** Standard patterns — all `gh pr create` flags and label operations are fully documented in FEATURES.md. No additional research needed.

### Phase Ordering Rationale

- Safety infrastructure precedes agents because the `affected_files` allowlist is a load-bearing constraint, not an add-on.
- Analyzer precedes all specialists because specialists receive their file scope from the Analyzer — building them in parallel would require mocking an interface that hasn't been validated.
- Reviewer precedes PR Creator because the `review_passed` flag is a required input to PR creation. Building PR Creator first tempts shortcuts.
- Observability (hooks, artifact upload) is bundled into Phase 5 rather than Phase 1 because it requires the full message stream to be meaningful; adding it earlier adds complexity without value.

### Research Flags

Phases needing deeper research during planning: none — all four researchers produced comprehensive, internally consistent findings. The main verification needed is runtime behavior of `ClaudeSDKClient` session resume semantics when a mid-pipeline crash occurs (Phases 1/2 boundary).

Phases with standard patterns (skip research-phase):
- Phase 1: GitHub Actions YAML is stable and fully covered.
- Phase 3: Test detection is language-agnostic and fully documented in ARCHITECTURE.md §8.
- Phase 5: `gh` CLI PR creation commands are stable since 2021.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All findings from primary source: installed SDK at `.venv/lib/python3.12/site-packages/claude_agent_sdk/`. No guessing. |
| Features | HIGH | GitHub Actions and `gh` CLI are stable, well-documented. Rate limit values verified (1,000 req/hour for GITHUB_TOKEN in Actions). |
| Architecture | HIGH | Patterns are established (multi-agent pipelines, append-only state, bounded tool allowlists). MEDIUM for specific SDK `allowedTools` scoping mechanics — verify at runtime. |
| Pitfalls | MEDIUM | Grounded in established AI agent safety patterns and GitHub Actions security literature. Specific cost estimates ($37K–135K tokens/issue) are approximations based on claude-sonnet-4 pricing as of early 2026 — validate after first few runs. |

**Overall confidence:** HIGH for structural decisions. MEDIUM for cost/token estimates and runtime edge cases in SDK session resume.

### Gaps to Address

- **Session resume crash recovery semantics:** STACK.md documents `resume=session_id` as a mechanism, but the exact behavior when the pipeline crashes mid-stage (e.g., between Analyzer and BugFixer) needs validation in Phase 1 integration testing. Fallback: use file-based `IssueContext` JSON as the source of truth for resume; session resume is optional optimization.

- **`allowed_tools` scoping for `Bash` subcommands:** ARCHITECTURE.md uses `"Bash:readonly"` and `"Bash:test_only"` as conceptual buckets. The actual enforcement is via system prompt instructions, not SDK-level tool filtering. This gap must be addressed in Phase 1 by defining explicit bash command allowlists in each stage's system prompt, not relying on the SDK to enforce them.

- **Token usage tracking API:** PITFALLS.md recommends a 150K token budget, but the exact field path to cumulative usage in `TaskProgressMessage.usage` needs verification against the live SDK. Check `ResultMessage` for a `usage` field at session end.

- **Bandit availability in GitHub Actions `ubuntu-latest`:** The security scan requires `bandit` for Python projects. It is not pre-installed. Phase 4 must include a conditional `pip install bandit` step, or use a pre-built GitHub Action.

---

## Sources

### Primary (HIGH confidence)
- `/home/utakata/ドキュメント/utakata-agent/.venv/lib/python3.12/site-packages/claude_agent_sdk/` — SDK types, client, query, errors, transport (direct source inspection)
- GitHub Actions documentation (training data — stable features)
- `gh` CLI documentation (training data — stable since 2021)

### Secondary (MEDIUM confidence)
- Training knowledge of autonomous agent architecture patterns (LangChain, AutoGPT, multi-agent safety literature)
- GitHub API rate limits: 1,000 req/hour for GITHUB_TOKEN in Actions (documented behavior, verified in FEATURES.md research)
- claude-sonnet-4 token pricing as of early 2026 (PITFALLS.md cost estimates — validate post-deployment)

### Tertiary (LOW confidence)
- `allowedTools` per-subcommand scoping mechanics in claude-agent-sdk v0.1.50 — inferred from SDK source, needs runtime verification
- Token budget enforcement via `TaskProgressMessage.usage` field path — needs verification against live SDK

---
*Research completed: 2026-03-22*
*Ready for roadmap: yes*
