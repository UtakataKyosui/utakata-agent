# Requirements: utakata-agent

## Milestone 1: issue-resolver — 実用可能な第一ワークフロー

### Overview

GitHub の open Issue を自律的に処理して PR を作成する AI Agent パイプラインを構築する。
`claude-agent-sdk` を使ったマルチエージェント構成で、任意のリポジトリに配置して GitHub Actions で動かせる。

---

## Functional Requirements

### FR-1: Issue 検知・取得
- open な Issue を定期スキャン（GitHub Actions cron）で取得できる
- 既に処理中の Issue（`agent-processing` ラベル）をスキップできる
- 完了済みの Issue（`agent-resolved` ラベル）をスキップできる
- 1回の実行で1件の Issue を処理する（レート制限対策）

### FR-2: Issue 分析（Analyzer Agent）
- Issue のタイトル・本文からコンテキストを読み取れる
- リポジトリのコードベースを探索して影響ファイルを特定できる
- Issue 種別を判定できる（`bug` / `feature` / `refactor`）
- 実装方針を生成できる（`IssueContext` として出力）
- 複雑すぎる Issue を検出してスキップ判定できる
  - 影響ファイル数 > 15
  - 影響ファイルの信頼度が低い
  - 曖昧すぎる記述

### FR-3: 専門エージェント（BugFixer / FeatureDev / Refactorer）
- Issue 種別に応じた専門エージェントにルーティングできる
- Analyzer が特定した影響ファイルの範囲内でのみコードを変更できる
- 変更後にテストを実行できる（テストが存在する場合）
- テストが失敗した場合は PR を作成せず中断する

### FR-4: コードレビュー（Reviewer Agent）
- 専門エージェントが行った変更をレビューできる
- 既存テストの変更・削除を検出して拒否できる
- セキュリティ上の問題を検出して拒否できる（bandit 相当）
- `review_passed: true` を明示的に出力する

### FR-5: PR 作成（PR Creator）
- `agent/issue-{number}-{short-description}` 形式でブランチを作成できる
- 変更内容をコミットできる（git identity: `github-actions[bot]`）
- `gh` CLI で PR を作成できる
- 元 Issue に PR リンクと処理サマリーをコメントできる
- Issue に `agent-resolved` ラベルを付与できる

### FR-6: プロジェクト構造
- このリポジトリが「ワークフロー集」として機能する
- 各ワークフローは独立したディレクトリ（`issue-resolver/` 等）に格納される
- `main.py` がエントリポイントとして各ワークフローを呼び出せる

---

## Non-Functional Requirements

### NFR-1: 安全性
- 1回の実行で消費するトークンの上限: 150,000 tokens
- エージェントの最大反復数: 5 iterations
- Analyzer が特定した影響ファイル以外は変更しない
- Issue 本文は `<issue_content>` で囲んで untrusted input として扱う（prompt injection 対策）
- PR 作成前に必ずセキュリティスキャン（`bandit`）を実行する

### NFR-2: 信頼性
- 無限ループ防止: `concurrency` グループ + ラベルロック + ブランチ/PR 存在チェック
- ロック状態から回復できる（2時間以上処理中の Issue は stale として解放）
- エラー時は Issue に `agent-failed` ラベルと失敗理由コメントを残す

### NFR-3: 汎用性
- 特定のプログラミング言語に依存しない
- テスト検出は言語別のマーカーファイルから行う
  - Python: `pyproject.toml`, `pytest.ini`
  - Node.js: `package.json` の `test` スクリプト
  - Rust: `Cargo.toml`
  - Go: `go.mod`
  - Ruby: `Gemfile`

### NFR-4: 可観測性
- `SubagentStart` / `SubagentStop` フックでエージェント実行をログに記録する
- 各 Issue の処理状態を GitHub Labels で可視化する
- PR 説明文に AI が行った判断の根拠を含める

---

## Technical Requirements

### TR-1: claude-agent-sdk 使用方針
- `ClaudeSDKClient`（双方向・ステートフル）を使用する（`query()` は使わない）
- エージェント定義は `AgentDefinition` + `ClaudeAgentOptions.agents` で行う
- 自律動作に `bypassPermissions` + 明示的な `allowed_tools` リストを設定する
- GitHub ツール（Issue 取得・ラベル操作・PR 作成）は `@tool` + `create_sdk_mcp_server()` でカスタム MCP ツール化する

### TR-2: エージェント間の引き渡し
- `IssueContext`（JSON シリアライズ可能な dataclass）を各ステージ間の標準引き渡し形式とする
- Analyzer write zone: `issue_type`, `affected_files`, `implementation_plan`, `complexity_score`
- Specialist write zone: `changes_made`, `tests_run`, `tests_passed`
- Reviewer write zone: `review_passed`, `review_notes`

### TR-3: GitHub Actions
- トリガー: `schedule` (cron) + `workflow_dispatch`（手動実行）
- 必要な権限: `contents: write`, `issues: write`, `pull-requests: write`
- シークレット: `GITHUB_TOKEN`（自動）, `ANTHROPIC_API_KEY`（手動設定）
- Git identity: `github-actions[bot]@users.noreply.github.com`

---

## Out of Scope (Milestone 1)

- 複数 Issue の並列処理
- Issue テンプレートへの対応
- PR の自動マージ
- 他のワークフロー（`issue-resolver` 以外）の開発

---

## Success Criteria

1. GitHub Actions の cron で起動し、open Issue を1件検出して PR を作成できる
2. テストが失敗する変更では PR を作成しない
3. 既存テストを変更・削除しない
4. セキュリティ問題のあるコードを含む PR を作成しない
5. 複雑すぎる Issue は処理をスキップして Issue にコメントを残せる
6. `issue-resolver/` ディレクトリが独立して動作し、他のワークフロー追加が容易な構造になっている
