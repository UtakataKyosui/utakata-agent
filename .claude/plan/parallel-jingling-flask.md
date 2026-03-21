# GSD New-Project Plan: utakata-agent

## Context

このリポジトリは **AI Agent ワークフロー集**。
各ディレクトリ = 1つのワークフロー（パイプライン）。
各ディレクトリ内に、そのワークフローを実現する専門エージェントが入っている。
まず第1ワークフローとして `issue-resolver/` を構築する。

---

## プロジェクト概要

| 項目 | 内容 |
|------|------|
| リポジトリの性質 | AI Agent ワークフローのプラグインマーケットプレイス的な集合体 |
| 最初のワークフロー | `issue-resolver/` — GitHub open Issue を自動解決して PR を作成 |
| 実行方法 | GitHub Actions (cron) + `main.py` でワークフローを起動 |
| 自律度 | フルオート（コード実装 → テスト → PR 作成まで） |
| Issue 種別 | バグ修正・新機能実装・リファクタリング |
| 対象言語 | 言語問わず（汎用） |

---

## プロジェクト構造

```
utakata-agent/               ← このリポジトリ
├── main.py                  ← エントリポイント（ワークフロー呼び出し）
├── pyproject.toml
├── uv.lock
│
├── issue-resolver/          ← 第1ワークフロー
│   ├── __init__.py
│   ├── run.py               ← このワークフローのエントリポイント
│   ├── orchestrator.py      ← Issue 一覧取得・ルーティング
│   ├── analyzer.py          ← Analyzer Agent（分析・分類）
│   ├── bug_fixer.py         ← BugFixer Agent（バグ修正特化）
│   ├── feature_dev.py       ← FeatureDev Agent（新機能実装特化）
│   ├── refactorer.py        ← Refactorer Agent（リファクタリング特化）
│   ├── reviewer.py          ← Reviewer Agent（コードレビュー）
│   └── pr_creator.py        ← PR Creator（git + gh CLI）
│
├── (future-workflow-1)/     ← 将来追加するワークフロー
│   └── ...
│
└── (future-workflow-2)/
    └── ...
```

---

## issue-resolver の Agent パイプライン

```
GitHub Actions (cron)
        ↓
  main.py → issue-resolver/run.py
        ↓
  orchestrator.py
  ├─ gh CLI で open Issue 一覧取得
  ├─ 未処理 Issue をフィルタ
  └─ For each Issue:
            ↓
     analyzer.py (Analyzer Agent)
     ・Issue テキスト解析
     ・コードベース探索 (Read/Grep/Glob のみ)
     ・Issue 種別判定（bug/feature/refactor）
     ・影響ファイル・実装方針を出力
            ↓
     Issue 種別でルーティング
     ┌────────────┬──────────────┬──────────────┐
     ↓            ↓              ↓
 bug_fixer  feature_dev    refactorer
 .py        .py            .py
 (BugFixer) (FeatureDev)   (Refactorer)
 ・実装      ・実装          ・実装
 ・テスト    ・テスト        ・テスト
     └────────────┴──────────────┴──────────────┘
            ↓
     reviewer.py (Reviewer Agent)
     ・コードレビュー
     ・テスト確認
            ↓
     pr_creator.py
     ・git ブランチ作成
     ・コミット
     ・gh CLI で PR 作成
     ・元 Issue にコメント
```

### 各 Agent の責務

| Agent | ツール | 役割 |
|-------|--------|------|
| orchestrator | Bash (gh CLI) | Issue 取得・状態管理・ルーティング |
| analyzer | Read, Grep, Glob | Issue 分析・コードベース探索・方針生成 |
| bug_fixer | Read, Edit, Write, Bash, Grep, Glob | バグ特定・修正・テスト実行 |
| feature_dev | Read, Edit, Write, Bash, Grep, Glob | 機能設計・実装・テスト作成 |
| refactorer | Read, Edit, Write, Bash, Grep, Glob | リファクタ計画・実施・テスト確認 |
| reviewer | Read, Grep, Glob, Bash | コードレビュー・品質チェック |
| pr_creator | Bash (git + gh CLI) | ブランチ作成・コミット・PR 作成 |

### claude-agent-sdk 活用方針
- `ClaudeSDKClient` で双方向・ステートフル会話
- `ClaudeAgentOptions.agents` に各専門エージェントを `AgentDefinition` で定義
- `SubagentStart/Stop` フックでエージェント実行を監視・ログ
- GitHub ツールは `@tool` + `create_sdk_mcp_server()` でカスタム MCP ツール化

---

## ロードマップ（想定フェーズ）

### Phase 1: コアアーキテクチャ
- プロジェクト構造セットアップ（`issue-resolver/` ディレクトリ）
- `main.py` にワークフロー呼び出し機構
- GitHub CLI ラッパー（Issue 取得・PR 作成）

### Phase 2: Analyzer Agent
- Issue テキスト解析ロジック
- コードベース探索（影響ファイル特定）
- Issue 種別分類（bug/feature/refactor）

### Phase 3: 専門エージェント群（BugFixer / FeatureDev / Refactorer）
- 各エージェントのプロンプト設計
- `AgentDefinition` でツール制限
- テスト実行機能

### Phase 4: Reviewer & PR Creator
- コードレビューエージェント
- git + gh CLI での PR 作成自動化
- Issue へのフィードバックコメント

### Phase 5: GitHub Actions ワークフロー
- `.github/workflows/issue-agent.yml`
- GITHUB_TOKEN, ANTHROPIC_API_KEY のシークレット管理
- cron スケジュール設定

### Phase 6: テスト & 堅牢化
- エラーハンドリング・リトライ
- 複雑すぎる Issue のスキップ機能
- ドライランモード（`--dry-run`）

---

## GSD ワークフロー実行内容（このプランが承認された後）

1. `gsd-tools.cjs init new-project` で初期化チェック
2. `.planning/PROJECT.md` 作成
3. `config.json` でワークフロー設定
4. リサーチエージェント起動（claude-agent-sdk・マルチエージェント・GitHub Actions）
5. `.planning/REQUIREMENTS.md` 作成
6. `.planning/ROADMAP.md` 作成（上記 6 フェーズ）
7. `.planning/STATE.md` 作成
8. 初期 git コミット

## 重要ファイル

- `main.py` — エントリポイント（現在 claude-agent-sdk の query サンプル）
- `pyproject.toml` — claude-agent-sdk v0.1.50 依存
