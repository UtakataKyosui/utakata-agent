# Roadmap: utakata-agent

## Milestone 1: issue-resolver — 実用可能な第一ワークフロー

---

## Phase 1: パイプライン骨格 & 安全基盤

**Goal:** エージェントが安全に動作するための骨格を作る。GitHub ラベルロック、`IssueContext` スキーマ、`ClaudeSDKClient` 基盤、pre-PR バリデーションゲートを構築する。この骨格なしにはどのエージェントも実装できない。

**Deliverables:**
- `issue-resolver/` ディレクトリ構造とモジュール骨格
- `IssueContext` dataclass（JSON シリアライズ可能、3ステージの write zone を持つ）
- GitHub MCP ツール（`@tool` + `create_sdk_mcp_server()`）
  - `list_open_issues()` — open かつ未処理の Issue 一覧取得
  - `claim_issue(number)` — `agent-processing` ラベルを付与
  - `release_issue(number, outcome)` — ラベルを resolved/skip/failed に更新
  - `create_branch(name)` — ブランチ作成
  - `create_pr(branch, title, body)` — PR 作成
  - `comment_on_issue(number, body)` — Issue にコメント
- Pre-PR バリデーション関数（4つの hard abort 条件）
  - セキュリティスキャン失敗
  - 既存テストの変更検出
  - トークン予算超過（150K tokens）
  - 複雑度閾値超過
- `ClaudeSDKClient` 基盤クラス（`bypassPermissions` + `allowed_tools`）
- `SubagentStart`/`SubagentStop` フックによるロギング

**UAT:**
- `list_open_issues()` が open な未処理 Issue を返す
- `claim_issue()` でラベルが付与され、次の `list_open_issues()` でスキップされる
- `IssueContext` が JSON にシリアライズ/デシリアライズできる
- 4つの hard abort 条件がそれぞれ独立してトリガーされる

**Plans:** 4/4 plans executed (Phase 1 Complete)

Plans:
- [x] 01-01-PLAN.md — Wave 0 test scaffold: pytest setup + 3 test files with failing tests
- [x] 01-02-PLAN.md — IssueContext dataclass + validate_pre_pr gate function (TDD)
- [x] 01-03-PLAN.md — GitHub MCP tools: 6 gh CLI wrappers + create_sdk_mcp_server (TDD)
- [x] 01-04-PLAN.md — AgentBase + module skeleton stubs + main.py ClaudeSDKClient update

---

## Phase 2: Analyzer Agent

**Goal:** Issue を読んでコードベースを探索し、影響ファイルと実装方針を出力する Analyzer を構築する。Analyzer の `affected_files` が後続エージェントの write 境界を決定するため、最も重要なコンポーネント。

**Deliverables:**
- `issue-resolver/analyzer.py` — Analyzer Agent 実装
  - Issue テキスト解析（タイトル・本文・ラベル）
  - コードベース探索（Read/Grep/Glob のみ使用）
  - Issue 種別判定（`bug` / `feature` / `refactor`）
  - 影響ファイル特定（信頼度付き、最大15件）
  - 実装方針生成
  - 複雑度スコア計算（0-10）
- `AgentDefinition` 設定（Analyzer 専用: Read/Grep/Glob のみ）
- `IssueContext.analyzer_output` への出力

**UAT:**
- バグ報告の Issue を渡すと `issue_type: "bug"` が返る
- `affected_files` に実際に関連するファイルが含まれる
- 影響ファイル15件超の Issue は `complexity_score > 8` になる
- Analyzer がファイルを変更しない（Read 系ツールのみ使用）

**Plans:** 4 plans

Plans:
- [ ] 02-01-PLAN.md — Wave 0 TDD test scaffold: tests/test_analyzer.py with all failing tests
- [ ] 02-02-PLAN.md — Pure helper functions: body fetch, prompt builder, label mapping, complexity score
- [ ] 02-03-PLAN.md — AnalyzerAgent.run() implementation with ClaudeSDKClient + output_format
- [ ] 02-04-PLAN.md — Pipeline wiring: run.py calls Analyzer + skip-score handling

---

## Phase 3: 専門エージェント群（BugFixer / FeatureDev / Refactorer）

**Goal:** Issue 種別ごとに最適化された実装エージェントを構築する。Analyzer の `affected_files` 範囲内でのみ動作し、テストを実行して結果を `IssueContext` に記録する。

**Deliverables:**
- `issue-resolver/bug_fixer.py` — BugFixer Agent
  - バグ原因の特定（デバッグ思考）
  - 最小限の変更で修正（`affected_files` の範囲内）
- `issue-resolver/feature_dev.py` — FeatureDev Agent
  - 機能設計 → 実装 → テスト作成
- `issue-resolver/refactorer.py` — Refactorer Agent
  - リファクタリング計画 → 段階的実施
- 共通機能（`issue-resolver/specialist_base.py`）
  - `AgentDefinition` 設定（Read/Edit/Write/Bash/Grep/Glob）
  - `allowed_tools` による影響ファイル外への書き込み防止（system prompt ベース）
  - 言語別テスト実行（pyproject.toml/package.json/Cargo.toml/go.mod/Gemfile 検出）
  - テスト結果を `IssueContext.specialist_output` に記録

**UAT:**
- BugFixer が `affected_files` 以外のファイルを変更しない
- テスト成功時に `tests_passed: true` が記録される
- テスト失敗時に pipeline が中断される
- FeatureDev が新機能にテストを追加する

---

## Phase 4: Reviewer Agent & Pre-PR バリデーション

**Goal:** 変更内容を独立してレビューし、PR 作成前の最後の安全ゲートを機能させる。Reviewer は必ず何らかの懸念点を探す（rubber-stamping 禁止）。

**Deliverables:**
- `issue-resolver/reviewer.py` — Reviewer Agent
  - コードレビュー（品質・セキュリティ・スコープ）
  - 既存テスト変更の検出（diff audit）
  - `bandit` によるセキュリティスキャン（Python の場合）
  - `review_passed: true/false` を明示的に出力
- Pre-PR バリデーション統合（Phase 1 で構築した関数との接続）
- `IssueContext.reviewer_output` への出力

**UAT:**
- 既存テストを削除する変更を渡すと `review_passed: false` になる
- `eval()` を含むコードを渡すと security scan で reject される
- クリーンな変更は `review_passed: true` になる
- `review_notes` に具体的な懸念点が記述される

---

## Phase 5: PR Creator & GitHub Actions ワークフロー

**Goal:** PR 作成を自動化し、GitHub Actions で定期実行できるようにする。エンドツーエンドのパイプラインを実際のリポジトリで動作させる。

**Deliverables:**
- `issue-resolver/pr_creator.py` — PR Creator
  - `agent/issue-{number}-{slug}` ブランチ作成
  - コミット（git identity: `github-actions[bot]@users.noreply.github.com`）
  - `gh` CLI で PR 作成（AI 生成であることを PR 説明に明記）
  - 元 Issue へのコメント（PR リンク + 処理サマリー）
  - Issue に `agent-resolved` ラベル付与
- `.github/workflows/issue-agent.yml`
  - trigger: `schedule` (1時間ごと) + `workflow_dispatch`
  - permissions: `contents: write`, `issues: write`, `pull-requests: write`
  - concurrency: `group: issue-agent` で並列実行を防止
  - Python + uv のセットアップ
  - シークレット: `ANTHROPIC_API_KEY`
- ラベルセットアップドキュメント（`agent-processing`, `agent-resolved`, `agent-skip`, `agent-failed`）

**UAT:**
- GitHub Actions で手動トリガー（`workflow_dispatch`）して Issue が処理される
- 同時実行した場合に2番目の実行がスキップされる
- 処理中に Actions を停止した場合、2時間後に stale ロックが解放される
- PR 説明文に AI 生成であることと処理の根拠が含まれる

---

## Phase 6: テスト & 堅牢化

**Goal:** エラーケースへの対応、コスト制御、ドライランモードを実装して本番運用に耐える品質にする。

**Deliverables:**
- ドライランモード（`--dry-run`）: PR 未作成で処理内容を出力のみ
- トークン予算モニタリング（150K tokens hard cap）
- リトライ機構（一時的なエラー: 最大3回）
- エラーレポート（`agent-failed` ラベル + 詳細コメント）
- stale ロック自動解放（2時間タイムアウト）
- 統合テスト（実際の GitHub Actions 環境でのE2E テスト）

**UAT:**
- `--dry-run` で実行してもファイル変更・PR 作成が行われない
- 150K tokens 超過で処理が中断され `agent-failed` ラベルが付く
- GitHub API エラー時に自動リトライされる（最大3回）

---

## Phase Summary

| Phase | Goal | Key Output |
|-------|------|-----------|
| 1 | パイプライン骨格 | 4/4 Complete |
| 2 | Issue 分析 | Analyzer Agent + 影響ファイル特定 |
| 3 | 専門実装 | BugFixer / FeatureDev / Refactorer |
| 4 | レビュー | Reviewer Agent + Pre-PR ゲート |
| 5 | 実行環境 | PR Creator + GitHub Actions workflow |
| 6 | 堅牢化 | ドライランモード + エラーハンドリング |
