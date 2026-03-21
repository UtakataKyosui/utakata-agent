# utakata-agent

## What This Is

GitHub の open Issue を自律的に処理して PR を作成する AI Agent ワークフロー集。
このリポジトリは「AIワークフロー・プラグインマーケットプレイス」として設計されており、
各ディレクトリが独立した AI Agent パイプライン（ワークフロー）を格納する。

最初のワークフロー: `issue-resolver/` — GitHub Issue を分析・実装・PR 作成まで全自動で行う。

## Core Value

対象リポジトリに配置して GitHub Actions で動かすだけで、open Issue を自動的に処理してくれる。
Issue を読んで、コードベースを理解し、実装し、テストし、PR を作成するまでを完全自動化する。

## Architecture

```
utakata-agent/               ← このリポジトリ（ワークフロー集）
├── main.py                  ← エントリポイント
├── issue-resolver/          ← 第1ワークフロー
│   ├── orchestrator.py      ← Issue 取得・ルーティング
│   ├── analyzer.py          ← Analyzer Agent
│   ├── bug_fixer.py         ← BugFixer Agent
│   ├── feature_dev.py       ← FeatureDev Agent
│   ├── refactorer.py        ← Refactorer Agent
│   ├── reviewer.py          ← Reviewer Agent
│   └── pr_creator.py        ← PR Creator
└── (future workflows)/
```

### Pipeline Flow (issue-resolver)
```
GitHub Actions (cron)
→ Orchestrator (Issue 取得・フィルタ)
→ Analyzer (Issue 分析・種別判定・影響ファイル特定)
→ [Bug|Feature|Refactor] Agent (実装・テスト)
→ Reviewer (コードレビュー)
→ PR Creator (ブランチ・コミット・PR 作成)
```

## Tech Stack

- **言語**: Python 3.12+
- **AI SDK**: `claude-agent-sdk` v0.1.50
- **Agent 管理**: `ClaudeSDKClient` + `AgentDefinition`
- **GitHub 統合**: `gh` CLI
- **実行環境**: GitHub Actions (cron)
- **パッケージマネージャ**: `uv`

## Constraints

- 汎用設計（対象リポジトリの言語を問わない）
- GitHub Actions で動かすことを前提
- `GITHUB_TOKEN` と `ANTHROPIC_API_KEY` のシークレットが必要
- フルオート（人間の介入なしに PR 作成まで完了）

## Success Criteria

- open Issue に対して自動的に PR が作成される
- Issue の種別（bug/feature/refactor）に応じた専門エージェントが処理する
- テストが通らない限り PR を作成しない
- 複雑すぎる Issue はスキップしてコメントを残す
