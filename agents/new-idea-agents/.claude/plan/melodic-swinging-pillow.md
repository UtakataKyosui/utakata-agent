# jj コミット + Lefthook 導入プラン

## Context

ESLint・Prettier の設定が完了したので:
1. その変更を jj でコミットする
2. Lefthook を導入して pre-commit フックで lint + format:check を自動実行する

jj はコロケーテッド Git リポジトリ（`.jj/` と `.git/` が共存）として動作しているため、
Lefthook が `.git/hooks/` にインストールするフックは jj からのコミット時にも有効になる。

## リポジトリ構成

```
/home/utakata/ドキュメント/utakata-agent/    ← リポジトリルート（.jj/ + .git/ あり）
└── agents/
    └── new-idea-agents/                      ← プロジェクトルート（package.json あり）
        ├── eslint.config.ts
        ├── .prettierrc
        ├── .prettierignore
        └── package.json
```

## 変更ファイル一覧

| ファイル | 場所 | 変更種別 |
|---|---|---|
| `lefthook.yml` | リポジトリルート | 新規作成 |
| `agents/new-idea-agents/package.json` | プロジェクト | `lefthook` devDependency 追加 + `postinstall` スクリプト追加 |

---

## Step 1: jj でコミット

```bash
# リポジトリルートで実行
cd /home/utakata/ドキュメント/utakata-agent
jj commit -m "feat(new-idea-agents): add ESLint and Prettier configuration"
```

コミット対象の変更:
- `agents/new-idea-agents/eslint.config.ts` — globals修正 + eslint-config-prettier 統合
- `agents/new-idea-agents/.prettierrc` — 新規作成
- `agents/new-idea-agents/.prettierignore` — 新規作成
- `agents/new-idea-agents/package.json` — lint/format スクリプト追加、devDependencies 追加
- `agents/new-idea-agents/index.ts` — unused catch variable 修正
- `agents/new-idea-agents/loader.ts` — let → const 修正

---

## Step 2: Lefthook インストール

```bash
cd agents/new-idea-agents
bun add -d lefthook
```

---

## Step 3: lefthook.yml をリポジトリルートに作成

**パス**: `/home/utakata/ドキュメント/utakata-agent/lefthook.yml`

```yaml
pre-commit:
  commands:
    lint:
      root: "agents/new-idea-agents/"
      run: bun run lint
    format-check:
      root: "agents/new-idea-agents/"
      run: bun run format:check
```

`root:` でコマンドの作業ディレクトリを指定し、リポジトリルートからでも正しく動作させる。

---

## Step 4: package.json に postinstall スクリプト追加

`bun install` 時に自動でフックがインストールされるよう設定:

```json
{
  "scripts": {
    "start": "bun index.ts",
    "test": "bun test",
    "lint": "eslint .",
    "lint:fix": "eslint . --fix",
    "format": "prettier --write \"**/*.{ts,js,json,md}\"",
    "format:check": "prettier --check \"**/*.{ts,js,json,md}\"",
    "postinstall": "lefthook install"
  }
}
```

---

## Step 5: フックのインストール実行

```bash
cd agents/new-idea-agents
bunx lefthook install
```

`.git/hooks/pre-commit` が作成される。

---

## Verification

```bash
# フックが正しくインストールされているか確認
ls /home/utakata/ドキュメント/utakata-agent/.git/hooks/pre-commit

# jj でコミットを試して pre-commit フックが発動するか確認
cd /home/utakata/ドキュメント/utakata-agent
jj describe -m "test: verify lefthook works"
# → lint と format:check が実行される
```
