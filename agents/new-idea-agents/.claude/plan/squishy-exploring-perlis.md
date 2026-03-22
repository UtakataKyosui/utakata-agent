# GitHub Actions 対応 実装計画

## Context

Claude Agent CLI を GitHub Actions 上で自動実行できるようにする。
Issue が開かれたら自動解決 PR を作成、PR が開かれたらレビューコメントを投稿。
まず現状の変更をコミットしてから、GHA 対応の修正を行う。

**SDK の確認済み前提**:
- `@anthropic-ai/claude-agent-sdk` v0.2.81 に Claude Code バイナリ (cli.js) が埋め込み済み
- 別途 `claude` CLI のインストール不要
- `bun install` だけで動作

---

## Step 1: 現状コミット

以下のファイルをステージして `git commit` する：

```
index.ts, loader.ts, stream.ts
loader.test.ts, stream.test.ts
agents/ask.md, agents/chat.md, agents/issue.md, agents/review.md, agents/meal.md
.gitignore, CLAUDE.md, README.md, package.json, tsconfig.json, bun.lock
.claude/settings.json
```

コミットメッセージ:
```
feat: add Claude Agent SDK-based CLI with agent definition system

- Dynamic agent discovery from .md files (built-in + ~/.claude/agents/)
- YAML frontmatter + template variables {{var}} for agent definitions
- SubAgent support via ## SubAgents section in .md files
- Built-in agents: ask, chat, issue (with subagents), review, meal
- Streaming output via AsyncGenerator<SDKMessage>
- TDD: 16 tests passing (stream, loader)
```

---

## Step 2: GitHub Actions 対応変更

### 2-1. `package.json` に scripts を追加

```json
"scripts": {
  "start": "bun index.ts",
  "test": "bun test"
}
```

### 2-2. `agents/issue.md` を更新

GHA で自動 PR 作成ができるよう、以下の指示を追加：

```markdown
**GitHub Actions での動作**:
修正完了後は以下の手順を実行してください：
1. `git checkout -b fix/issue-<番号>`
2. `git add -A && git commit -m "fix: <修正内容> (closes #<番号>)"`
3. `gh pr create --title "fix: <修正内容>" --body "Closes #<Issue番号>"`
```

Issue 番号は URL から抽出: `{{url}}` の末尾の数値。

### 2-3. `agents/review.md` を更新

GHA でレビューコメントを PR に投稿するよう指示を追加：

```markdown
**GitHub Actions での動作**:
レビュー完了後は以下で PR にコメントを投稿してください：
`gh pr review <PR番号> --comment --body "<レビュー内容>"`
または Approve/Request Changes:
`gh pr review <PR番号> --approve`
`gh pr review <PR番号> --request-changes --body "<コメント>"`
```

### 2-4. GitHub Actions ワークフローファイルを作成

#### `.github/workflows/issue-resolver.yml`

```yaml
name: Issue Auto-Resolver

on:
  issues:
    types: [opened, labeled]
  issue_comment:
    types: [created]

permissions:
  contents: write
  pull-requests: write
  issues: write

jobs:
  resolve:
    if: |
      (github.event_name == 'issues') ||
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '/resolve'))
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}
          fetch-depth: 0

      - uses: oven-sh/setup-bun@v2

      - run: bun install

      - name: Run Issue Resolver Agent
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          ISSUE_URL="${{ github.event.issue.html_url || github.event.comment.issue_url }}"
          bun index.ts issue "$ISSUE_URL" --cwd ${{ github.workspace }}
```

#### `.github/workflows/pr-reviewer.yml`

```yaml
name: PR Auto-Reviewer

on:
  pull_request:
    types: [opened, synchronize]

permissions:
  pull-requests: write
  contents: read

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: oven-sh/setup-bun@v2

      - run: bun install

      - name: Run PR Reviewer Agent
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          bun index.ts review "${{ github.event.pull_request.html_url }}"
```

#### `.github/workflows/manual-agent.yml`

```yaml
name: Manual Agent

on:
  workflow_dispatch:
    inputs:
      command:
        description: 'コマンド (ask / chat / meal)'
        required: true
        type: choice
        options: [ask, chat, meal]
      prompt:
        description: 'プロンプト / 質問内容'
        required: true
        type: string
      constraint:
        description: '制約 (meal コマンド用)'
        required: false
        type: string

permissions:
  contents: read

jobs:
  run-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: oven-sh/setup-bun@v2

      - run: bun install

      - name: Run Agent
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          CMD="${{ inputs.command }}"
          PROMPT="${{ inputs.prompt }}"
          CONSTRAINT="${{ inputs.constraint }}"

          if [ "$CMD" = "meal" ] && [ -n "$CONSTRAINT" ]; then
            bun index.ts meal "$PROMPT" --constraint "$CONSTRAINT"
          else
            bun index.ts "$CMD" "$PROMPT"
          fi
```

---

## Step 3: README.md の更新

GitHub Actions のセットアップ方法を追記：

```markdown
## GitHub Actions での使用

### 必要なシークレット

リポジトリの Settings > Secrets and variables > Actions に設定:

| シークレット名 | 説明 |
|--------------|------|
| `ANTHROPIC_API_KEY` | Anthropic API キー |

### 自動実行

- **Issue 自動解決**: Issue 作成時に自動起動、修正 PR を作成
- **PR 自動レビュー**: PR 作成/更新時に自動レビューコメント投稿
- **手動実行**: Actions タブから `Manual Agent` を選択
```

---

## 変更が必要なファイル一覧

| ファイル | 操作 | 内容 |
|---------|------|------|
| `package.json` | 修正 | scripts フィールドを追加 |
| `agents/issue.md` | 修正 | 自動 PR 作成の指示を追加 |
| `agents/review.md` | 修正 | PR コメント投稿の指示を追加 |
| `.github/workflows/issue-resolver.yml` | 新規 | Issue 自動解決ワークフロー |
| `.github/workflows/pr-reviewer.yml` | 新規 | PR 自動レビューワークフロー |
| `.github/workflows/manual-agent.yml` | 新規 | 手動実行ワークフロー |
| `README.md` | 修正 | GHA セットアップ説明を追加 |

---

## 検証方法

1. `bun test` → 16テスト全パス
2. `bun index.ts --help` → 全コマンドが表示される
3. GHA ワークフロー構文チェック: `gh workflow list` または GitHub UI で確認
4. 手動実行: Actions タブ > Manual Agent > Run workflow
5. 統合テスト: テストリポジトリで Issue を作成して動作確認
