# utakata-agent

Claude Agent SDK を使った汎用 CLI。Issue 解決・PR レビュー・食事提案など様々な用途に使えます。

## セットアップ

```bash
bun install
```

## 使い方

```bash
# ワンショット質問
bun index.ts ask "TypeScriptのtypeとinterfaceの違いは？"

# 汎用チャット
bun index.ts chat "このコードを説明して"

# GitHub Issue 解決（コードを自動修正して PR を作成）
bun index.ts issue https://github.com/owner/repo/issues/1 --cwd ./repo

# PR レビュー
bun index.ts review https://github.com/owner/repo/pull/42

# 食事提案
bun index.ts meal "夕食" --constraint "糖質制限"
```

## エージェントの追加

`agents/*.md` にファイルを追加するだけで新しいコマンドとして自動登録されます。
`~/.claude/agents/*.md` のユーザーレベルエージェントも自動検出されます。

```markdown
---
name: my-agent
description: カスタムエージェントの説明
tools:
  - Read
  - Bash
args:
  - name: input
    description: 入力
    required: true
    positional: true
---

あなたは{{input}}を処理するエージェントです。
```

## テスト

```bash
bun test
```

## GitHub Actions での使用

### 必要なシークレット

リポジトリの **Settings > Secrets and variables > Actions** に設定:

| シークレット名      | 説明               |
| ------------------- | ------------------ |
| `ANTHROPIC_API_KEY` | Anthropic API キー |

`GITHUB_TOKEN` は自動で提供されます。

### 自動実行ワークフロー

| ワークフロー         | トリガー                           | 動作                         |
| -------------------- | ---------------------------------- | ---------------------------- |
| `issue-resolver.yml` | Issue 作成時 / `/resolve` コメント | 自動修正して PR 作成         |
| `pr-reviewer.yml`    | PR 作成・更新時                    | レビューコメントを PR に投稿 |
| `manual-agent.yml`   | Actions タブから手動実行           | ask / chat / meal を実行     |
