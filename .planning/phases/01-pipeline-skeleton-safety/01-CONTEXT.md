# Phase 1: パイプライン骨格 & 安全基盤 - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

GitHub ラベルロック、`IssueContext` スキーマ、`ClaudeSDKClient` 基盤、GitHub MCP ツール群、pre-PR バリデーションゲートを構築する。この骨格なしには後続フェーズのどのエージェントも実装できない。Analyzer・Specialist・Reviewer の実装は含まない。

</domain>

<decisions>
## Implementation Decisions

### IssueContext スキーマ
- **フラットな1クラス** — ネストなし。全フィールドを1つの dataclass に持つ
- **Analyzer write zone フィールド:** `issue_type` (str: "bug"/"feature"/"refactor"), `affected_files` (list[str]: ファイルパスのみ、最大15件), `implementation_plan` (str), `complexity_score` (float: 0-10)
- **Specialist write zone フィールド:** `changes_made` (list[str]: 変更ファイルパスリスト), `tests_run` (bool), `tests_passed` (bool), `error_message` (str | None)
- **Reviewer write zone フィールド:** `review_passed` (bool | None: 未設定時は abort扱い), `review_notes` (str), `security_issues` (list[str])
- **メタデータフィールド（トップレベル）:** `issue_number` (int), `issue_title` (str), `started_at` (str: ISO 8601)
- **ミュータブル** — 各ステージが自分のフィールドに書き込む。frozen dataclass ではない
- **JSON シリアライズ:** `to_json()` / `from_json()` メソッドを持つ（パイプライン再開・デバッグ用）
- `affected_files` 上限: 15件（REQUIREMENTS.md の値を踏襲）
- 信頼度は各ファイルに持たない — `complexity_score` で全体判定

### GitHub MCP ツール
- **実装方針:** `gh` CLI を `subprocess.run(args_list, ...)` で直接呼び出す。`shell=False` で呼び出すことで shell injection を防止（引数はリスト渡し）
- **エラー処理:** GitHub API / gh CLI 失敗時は例外を raise。Pipeline 上位層でキャッチして `agent-failed` ラベルを付与する
- **`list_open_issues()` 返り値:** `[{'number': int, 'title': str, 'labels': list[str]}]` — body は含まない（Analyzer が別途取得する）
- `@tool` デコレータ + `create_sdk_mcp_server()` でエージェントからカスタムツールとして呼び出せる形にする
- **実装する6ツール:** `list_open_issues()`, `claim_issue(number)`, `release_issue(number, outcome)`, `create_branch(name)`, `create_pr(branch, title, body)`, `comment_on_issue(number, body)`

### Pre-PR バリデーション
- **単一ゲート関数:** `validate_pre_pr(ctx: IssueContext) -> None` — 4条件を順番にチェックし、最初の失敗で例外を raise
- **4つの hard abort 条件（チェック順）:**
  1. **affected_files 外変更検出:** `git diff --name-only` で変更ファイルを取得し、`affected_files` に含まれないファイルへの変更があれば abort
  2. **既存テスト変更検出:** `git diff --name-only` の結果に `test_*.py` / `*_test.py` / `*.test.*` / `tests/` 配下のファイルが含まれれば abort
  3. **セキュリティスキャン:** 対象リポジトリが Python の場合（pyproject.toml / pytest.ini 存在確認）は `bandit -ll` (MEDIUM以上) を実行して警告があれば abort。Python 以外はスキップ（将来フェーズで拡張）
  4. **トークン予算超過:** SDK の usage カウンタから累積トークン数を取得し、150,000 tokens 超過なら abort
- **失敗時ラベル:** すべての失敗を `agent-failed` に統一。失敗理由は Issue コメントの内容で区別する
- 複雑度閾値: `complexity_score > 8` でスキップ（Orchestrator 層で判定。validate_pre_pr の責務外）

### ClaudeSDKClient 基盤クラス
- **共通基底クラス:** `AgentBase` — `bypassPermissions` + `allowed_tools` + SubagentStart/SubagentStop ログフックを保持
- 各エージェント（Analyzer, BugFixer, FeatureDev, Refactorer, Reviewer）が `AgentBase` を継承する
- **ロギング:** `SubagentStart` / `SubagentStop` フックで `print()` を使って stdout に出力のみ（GitHub Actions のログに表示される）

### Phase 1 の完成度
- **GitHub ツールは実際に動く実装** — モックではなく実際の gh CLI を呼び出す。Phase 1 UAT は実際の GitHub リポジトリに対して確認する
- **`main.py` を修正:** `query()` → `ClaudeSDKClient` に差し替える（STATE.md の決定済み事項）
- **モジュール骨格:** `issue-resolver/` ディレクトリを作成し、各モジュールファイルを作成するが、Analyzer/Specialist/Reviewer の実装ロジックは Phase 1 のスコープ外（stub 関数として定義のみ）

### Claude's Discretion
- `AgentBase` の具体的なメソッド名・シグネチャ設計
- `IssueContext` の `to_json()` / `from_json()` の実装詳細（dataclasses.asdict 等）
- ログのフォーマット（タイムスタンプ形式、ログメッセージ内容）
- `validate_pre_pr()` の例外クラス設計（カスタム例外 vs 標準 ValueError）

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `pyproject.toml`: `claude-agent-sdk>=0.1.50` が依存関係に追加済み — パッケージインストール不要
- `main.py`: 現在 `query()` を使用 — Phase 1 で `ClaudeSDKClient` に差し替える

### Established Patterns
- パッケージマネージャ: `uv` — `uv run` でスクリプト実行
- Python 3.12+ 必須

### Integration Points
- `main.py` → `issue-resolver/run.py` を呼び出す設計（PROJECT.md の architecture）
- `issue-resolver/` ディレクトリが存在しない — Phase 1 で新規作成

</code_context>

<specifics>
## Specific Ideas

- GitHub ツールは `gh` CLI で統一（PyGitHub 等の追加ライブラリなし）
- IssueContext の write zone は「誰がいつ書いていいか」をコメントで明示する

</specifics>

<deferred>
## Deferred Ideas

- 複数言語向けセキュリティスキャン（bandit 以外）— Phase 6 以降で拡張
- stale ロック自動解放（2時間タイムアウト）— Phase 6 のスコープ
- `--dry-run` モード — Phase 6 のスコープ

</deferred>

---

*Phase: 01-pipeline-skeleton-safety*
*Context gathered: 2026-03-22*
