---
phase: 1
slug: pipeline-skeleton-safety
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (Wave 0 で pyproject.toml に追加) |
| **Config file** | なし — Wave 0 で作成 |
| **Quick run command** | `uv run pytest tests/test_context.py tests/test_validation.py -x -q` |
| **Full suite command** | `uv run pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_context.py tests/test_validation.py -x -q`
- **After every plan wave:** Run `uv run pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| W0-setup | 00 | 0 | Wave0 | setup | `uv run pytest tests/ -x -q` | ❌ W0 | ⬜ pending |
| context-schema | 01 | 1 | UAT-3 | unit | `uv run pytest tests/test_context.py::test_issue_context_json_roundtrip -x` | ❌ W0 | ⬜ pending |
| github-tools | 01 | 1 | UAT-1,UAT-2 | unit | `uv run pytest tests/test_github_tools.py -x` | ❌ W0 | ⬜ pending |
| validate-pre-pr | 01 | 1 | UAT-4a,4b,4c,4d | unit | `uv run pytest tests/test_validation.py -x` | ❌ W0 | ⬜ pending |
| agent-base | 02 | 2 | ClaudeSDKClient基盤 | unit | `uv run pytest tests/ -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — テストパッケージ初期化
- [ ] `tests/test_context.py` — IssueContext の JSON ラウンドトリップ、フィールドデフォルト値テスト
- [ ] `tests/test_validation.py` — 4条件の独立テスト（subprocess.run モック使用）
- [ ] `tests/test_github_tools.py` — list_open_issues/claim_issue の単体テスト（gh CLI モック）
- [ ] `pyproject.toml` への pytest 追加: `uv add --dev pytest`
- [ ] `issue-resolver/__init__.py` — パッケージ初期化

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| `list_open_issues()` が実際の GitHub リポジトリから取得 | UAT-1 | GitHub API アクセスが必要（CI 環境でのみ可能） | `GITHUB_TOKEN` を設定して `uv run python -c "from issue_resolver.github_tools import list_open_issues; print(list_open_issues())"` を実行 |
| `claim_issue()` でラベルが付与されスキップされる | UAT-2 | GitHub API アクセスが必要 | 実際の Issue 番号を使って `claim_issue(N)` を呼び出し、GitHub UI でラベルを確認 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
