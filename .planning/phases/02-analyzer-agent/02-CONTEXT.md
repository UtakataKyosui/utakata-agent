# Phase 2: Analyzer Agent - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

GitHub Issue を読んでコードベースを探索し、`IssueContext` の Analyzer write zone（`issue_type`, `affected_files`, `implementation_plan`, `complexity_score`）を埋める。ファイル変更は行わない（Read/Grep/Glob のみ使用）。Issue の複雑度を判定してスキップ候補を返すまでが責務。PR 作成・コード変更・テスト実行は後続フェーズ。

</domain>

<decisions>
## Implementation Decisions

### スキップ判定の厳格さ
- **積極的に捨てる方針** — 曖昧すぎる Issue（再現手順なし、50文字未満の本文、「そこを直して」程度の記述）はすぐスキップ判定
- **低信頼度の定義** — `affected_files` の内容で判断: 設定ファイル（*.json, *.yaml, *.toml 等）や非関連モジュール全幅が多数含まれる場合は低信頼度とみなす
- **スキップの伝達方法** — Analyzer は `complexity_score` を高く設定して返す（例: 11.0）。Pipeline 側（Orchestrator）がスコアを見てスキップ判定する。Analyzer 自身は例外を raise しない
- **スキップ時のコメント** — Issue に必ずコメントを残す。「情報不足のため自動処理できませんでした。再現手順・期待される動作・実際の動作を記載してください」パターンで返信

### 実装方針の詳細度
- **ステップバイステップリスト形式** — `implementation_plan` は番号付きステップ形式（3〜7ステップ目安）
- **テスト戦略を含める** — 実行すべきテストコマンド（例: `pytest tests/test_foo.py::test_null_check`）を方針に明記。Specialist が推測不要になる
- **コードも読んで定式化** — `affected_files` 特定後、実際にそのファイルを Read して関数シグネチャ・依存関係を確認した上で方針を記述。Issue 本文だけでは書かない

### Issue 種別判定の優先順位
- **ラベル優先** — GitHub ラベルが付いていればそれを使う。テキスト解析より信頼性が高い
- **固定マッピングテーブル:**
  - `bug` → `"bug"`
  - `enhancement`, `feature` → `"feature"`
  - `refactor`, `chore`, `cleanup`, `tech-debt` → `"refactor"`
  - マッピング外ラベルはテキスト解析フォールバックに移行
- **ラベルなし時** — タイトル + 本文を LLM（Analyzer 自身）が判定。キーワードマッチではなく文脈理解で判断

### 影響ファイル上限超過の扱い
- **15件超過時の動作** — `affected_files` を Issue との関連度順に並べ、上位15件にトリム。`complexity_score` を 8.0 超（例: 9.0〜11.0）に設定して返す。Pipeline 側がスコアを見てスキップ判断
- **上位15件の選択基準** — Issue 本文キーワード・タイトルとの意味的関連度が高いファイルを優先。テストファイルは対応するソースファイルとセットで扱う
- **コメント** — 15件超過を検出した場合、Issue に「影響範囲が広すぎるため自動処理は困難と判断しました（候補ファイル N 件）。スコープを絞り込んで Issue を分割することを推奨します」とコメント

### Claude's Discretion
- コードベース探索の具体的な Grep クエリ・Glob パターンの設計
- `complexity_score` の詳細な計算式（影響ファイル数・信頼度・Issue 曖昧さの重み付け）
- `affected_files` のソート順（Specialist が先頭から読む前提での並び順）

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AgentBase._make_options()`: bypassPermissions + SubagentStart/SubagentStop ログフック付き `ClaudeAgentOptions` を返す。`AnalyzerAgent` は継承して使える
- `AnalyzerAgent` stub (`issue_resolver/analyzer.py`): `allowed_tools = ["Read", "Grep", "Glob"]` が既に定義済み。`async def run(ctx: IssueContext) -> IssueContext` シグネチャを実装するだけ
- `IssueContext` (`issue_resolver/context.py`): Analyzer write zone フィールド（`issue_type`, `affected_files`, `implementation_plan`, `complexity_score`）が dataclass で定義済み。`to_json()` / `from_json()` あり

### Established Patterns
- **AgentBase 継承パターン** — `class AnalyzerAgent(AgentBase)` → `allowed_tools` 上書き → `run()` 実装のみ。`_make_options()` を呼ぶだけでフック・権限設定が完了する
- **bypassPermissions + allowed_tools** — Phase 1 で確立。Analyzer は `["Read", "Grep", "Glob"]` のみ。Write 系ツールは含めない
- **IssueContext append-only** — 各エージェントは自分の write zone にのみ書き込む。他ゾーンは読み取り専用

### Integration Points
- `issue_resolver/run.py` から `AnalyzerAgent().run(ctx)` として呼ばれる
- `list_open_issues()` は Issue body を含まない → Analyzer が GitHub MCP ツール経由で本文を個別取得する必要あり（`get_issue_body` 相当のツールが必要か、またはシステムプロンプト経由で渡す設計とするか、Phase 1 の `github_tools.py` 確認が必要）
- スキップ判定後の `comment_on_issue()` 呼び出しは GitHub MCP ツール（Phase 1 実装済み）を使う

</code_context>

<specifics>
## Specific Ideas

- スキップ時の Issue コメントは「情報不足のため自動処理できませんでした。再現手順・期待される動作・実際の動作を記載してください」パターン
- 15件超過スキップ時のコメントは「影響範囲が広すぎるため自動処理は困難と判断しました（候補ファイル N 件）。スコープを絞り込んで Issue を分割することを推奨します」パターン

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-analyzer-agent*
*Context gathered: 2026-03-22*
