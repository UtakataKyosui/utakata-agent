# Phase 1: パイプライン骨格 & 安全基盤 - Research

**Researched:** 2026-03-22
**Domain:** claude-agent-sdk (ClaudeSDKClient, @tool, create_sdk_mcp_server, hooks), Python dataclasses, subprocess/gh CLI, bandit
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### IssueContext スキーマ
- フラットな1クラス — ネストなし。全フィールドを1つの dataclass に持つ
- Analyzer write zone フィールド: `issue_type` (str: "bug"/"feature"/"refactor"), `affected_files` (list[str]: ファイルパスのみ、最大15件), `implementation_plan` (str), `complexity_score` (float: 0-10)
- Specialist write zone フィールド: `changes_made` (list[str]: 変更ファイルパスリスト), `tests_run` (bool), `tests_passed` (bool), `error_message` (str | None)
- Reviewer write zone フィールド: `review_passed` (bool | None: 未設定時は abort扱い), `review_notes` (str), `security_issues` (list[str])
- メタデータフィールド（トップレベル）: `issue_number` (int), `issue_title` (str), `started_at` (str: ISO 8601)
- ミュータブル — 各ステージが自分のフィールドに書き込む。frozen dataclass ではない
- JSON シリアライズ: `to_json()` / `from_json()` メソッドを持つ（パイプライン再開・デバッグ用）
- `affected_files` 上限: 15件（REQUIREMENTS.md の値を踏襲）
- 信頼度は各ファイルに持たない — `complexity_score` で全体判定

#### GitHub MCP ツール
- 実装方針: `gh` CLI を `subprocess.run(args_list, ...)` で直接呼び出す。`shell=False` で呼び出すことで shell injection を防止（引数はリスト渡し）
- エラー処理: GitHub API / gh CLI 失敗時は例外を raise。Pipeline 上位層でキャッチして `agent-failed` ラベルを付与する
- `list_open_issues()` 返り値: `[{'number': int, 'title': str, 'labels': list[str]}]` — body は含まない
- `@tool` デコレータ + `create_sdk_mcp_server()` でエージェントからカスタムツールとして呼び出せる形にする
- 実装する6ツール: `list_open_issues()`, `claim_issue(number)`, `release_issue(number, outcome)`, `create_branch(name)`, `create_pr(branch, title, body)`, `comment_on_issue(number, body)`

#### Pre-PR バリデーション
- 単一ゲート関数: `validate_pre_pr(ctx: IssueContext) -> None` — 4条件を順番にチェックし、最初の失敗で例外を raise
- 4つの hard abort 条件（チェック順）:
  1. affected_files 外変更検出: `git diff --name-only` で変更ファイルを取得し、`affected_files` に含まれないファイルへの変更があれば abort
  2. 既存テスト変更検出: `git diff --name-only` の結果に `test_*.py` / `*_test.py` / `*.test.*` / `tests/` 配下のファイルが含まれれば abort
  3. セキュリティスキャン: 対象リポジトリが Python の場合（pyproject.toml / pytest.ini 存在確認）は `bandit -ll` (MEDIUM以上) を実行して警告があれば abort。Python 以外はスキップ
  4. トークン予算超過: SDK の usage カウンタから累積トークン数を取得し、150,000 tokens 超過なら abort
- 失敗時ラベル: すべての失敗を `agent-failed` に統一。失敗理由は Issue コメントの内容で区別する
- 複雑度閾値: `complexity_score > 8` でスキップ（Orchestrator 層で判定。validate_pre_pr の責務外）

#### ClaudeSDKClient 基盤クラス
- 共通基底クラス: `AgentBase` — `bypassPermissions` + `allowed_tools` + SubagentStart/SubagentStop ログフックを保持
- 各エージェント（Analyzer, BugFixer, FeatureDev, Refactorer, Reviewer）が `AgentBase` を継承する
- ロギング: `SubagentStart` / `SubagentStop` フックで `print()` を使って stdout に出力のみ

#### Phase 1 の完成度
- GitHub ツールは実際に動く実装 — モックではなく実際の gh CLI を呼び出す
- `main.py` を修正: `query()` → `ClaudeSDKClient` に差し替える
- モジュール骨格: `issue-resolver/` ディレクトリを作成し、各モジュールファイルを作成するが、Analyzer/Specialist/Reviewer の実装ロジックは Phase 1 のスコープ外（stub 関数として定義のみ）

### Claude's Discretion
- `AgentBase` の具体的なメソッド名・シグネチャ設計
- `IssueContext` の `to_json()` / `from_json()` の実装詳細（dataclasses.asdict 等）
- ログのフォーマット（タイムスタンプ形式、ログメッセージ内容）
- `validate_pre_pr()` の例外クラス設計（カスタム例外 vs 標準 ValueError）

### Deferred Ideas (OUT OF SCOPE)
- 複数言語向けセキュリティスキャン（bandit 以外）— Phase 6 以降で拡張
- stale ロック自動解放（2時間タイムアウト）— Phase 6 のスコープ
- `--dry-run` モード — Phase 6 のスコープ
</user_constraints>

---

## Summary

Phase 1 は後続フェーズのすべてのエージェントが依存するインフラ層を構築する。主要な作業は4つ: (1) `IssueContext` dataclass の定義、(2) GitHub MCP ツール群（gh CLI ラッパー）、(3) `AgentBase` 基盤クラス（hooks 込み）、(4) `validate_pre_pr()` ゲート関数。これらはすべて独立して実装・テストできる。

`claude-agent-sdk` v0.1.50 をソースから確認済み。`@tool` デコレータと `create_sdk_mcp_server()` は `__init__.py` に直接定義されており、インポートは `from claude_agent_sdk import tool, create_sdk_mcp_server` で行う。`ClaudeAgentOptions` の `permission_mode="bypassPermissions"` と `allowed_tools` リストが自律動作の正しい設定。`SubagentStart` / `SubagentStop` は `HookEvent` 型として `types.py` に定義済み — フックは `ClaudeAgentOptions(hooks={...})` で渡す。

**Primary recommendation:** SDK ソースから確認した型・シグネチャを直接使用する。ドキュメントや外部情報への依存は不要。

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `claude-agent-sdk` | >=0.1.50 | ClaudeSDKClient, @tool, create_sdk_mcp_server | プロジェクト決定済み、pyproject.toml に記載 |
| `dataclasses` (stdlib) | Python 3.12+ | IssueContext スキーマ | 追加依存なし、JSON シリアライズが容易 |
| `subprocess` (stdlib) | Python 3.12+ | gh CLI 呼び出し | 決定済み（shell=False でリスト渡し） |
| `json` (stdlib) | Python 3.12+ | IssueContext to_json/from_json | 追加依存なし |
| `bandit` | latest | Python セキュリティスキャン | FR-4 / NFR-1 要件 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `mcp` | (sdk依存) | Server class（create_sdk_mcp_serverが内部使用） | @tool + create_sdk_mcp_server を使う場合に自動で必要 |
| `datetime` (stdlib) | Python 3.12+ | ISO 8601 タイムスタンプ生成 | started_at フィールドの生成 |
| `re` (stdlib) | Python 3.12+ | テストファイルパターンマッチ | validate_pre_pr のテスト変更検出 |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| subprocess + gh CLI | PyGitHub ライブラリ | 決定済み: gh CLI で統一（追加依存なし）|
| dataclass | Pydantic BaseModel | 決定済み: stdlib dataclass で十分 |
| カスタム例外 | ValueError | Claude's Discretion — 後述 |

**Installation:**
```bash
# bandit のみ追加が必要（他は既存 or stdlib）
uv add bandit
```

---

## Architecture Patterns

### Recommended Project Structure
```
issue-resolver/
├── __init__.py          # パッケージ初期化
├── run.py               # エントリポイント（main.py から呼び出し）
├── context.py           # IssueContext dataclass
├── github_tools.py      # @tool + create_sdk_mcp_server (GitHub MCP)
├── agent_base.py        # AgentBase 基盤クラス
├── validation.py        # validate_pre_pr() ゲート関数
├── analyzer.py          # stub のみ（Phase 2 で実装）
├── specialist.py        # stub のみ（Phase 3 で実装）
└── reviewer.py          # stub のみ（Phase 4 で実装）
```

### Pattern 1: @tool + create_sdk_mcp_server によるカスタム MCP ツール定義

**What:** `@tool` デコレータで非同期ハンドラを `SdkMcpTool` オブジェクトに変換し、`create_sdk_mcp_server()` でまとめて `McpSdkServerConfig` を生成する。これを `ClaudeAgentOptions(mcp_servers={"github": config})` に渡す。

**When to use:** エージェントから呼び出せるカスタムツールを定義するとき。

**Example:**
```python
# Source: /home/utakata/ドキュメント/utakata-agent/.venv/lib/python3.12/site-packages/claude_agent_sdk/__init__.py
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions

@tool("list_open_issues", "List open unprocessed issues", {})
async def list_open_issues(args: dict) -> dict:
    result = subprocess.run(
        ["gh", "issue", "list", "--state", "open", "--json", "number,title,labels"],
        capture_output=True, text=True, check=True
    )
    issues = json.loads(result.stdout)
    # Filter out agent-processing, agent-resolved, agent-skip, agent-failed
    ...
    return {"content": [{"type": "text", "text": json.dumps(filtered)}]}

github_server = create_sdk_mcp_server(
    name="github",
    version="1.0.0",
    tools=[list_open_issues, claim_issue, release_issue,
           create_branch, create_pr, comment_on_issue]
)

options = ClaudeAgentOptions(
    mcp_servers={"github": github_server},
    allowed_tools=["list_open_issues", "claim_issue", ...],
    permission_mode="bypassPermissions",
)
```

### Pattern 2: SubagentStart / SubagentStop フック登録

**What:** `ClaudeAgentOptions(hooks={"SubagentStart": [...], "SubagentStop": [...]})` で Hook を登録。Hook コールバックは `HookCallback` 型 = `async def f(input: HookInput, tool_use_id: str | None, context: HookContext) -> HookJSONOutput`。

**When to use:** エージェント開始・終了のロギング。

**Example:**
```python
# Source: types.py — HookEvent / HookMatcher / SubagentStartHookInput
from claude_agent_sdk import HookMatcher, ClaudeAgentOptions
from claude_agent_sdk.types import SubagentStartHookInput, SubagentStopHookInput, SyncHookJSONOutput

async def on_subagent_start(input, tool_use_id, context) -> SyncHookJSONOutput:
    # input は SubagentStartHookInput: agent_id, agent_type が必須フィールド
    print(f"[SubagentStart] agent_id={input['agent_id']} type={input['agent_type']}")
    return {"continue_": True}

async def on_subagent_stop(input, tool_use_id, context) -> SyncHookJSONOutput:
    print(f"[SubagentStop] agent_id={input['agent_id']} type={input['agent_type']}")
    return {"continue_": True}

options = ClaudeAgentOptions(
    hooks={
        "SubagentStart": [HookMatcher(hooks=[on_subagent_start])],
        "SubagentStop":  [HookMatcher(hooks=[on_subagent_stop])],
    },
    permission_mode="bypassPermissions",
    allowed_tools=[...],
)
```

### Pattern 3: IssueContext dataclass — to_json / from_json

**What:** `dataclasses.asdict()` で dict 変換 → `json.dumps()` でシリアライズ。`from_json()` は `json.loads()` + `**kwargs` でデシリアライズ。

**When to use:** ステージ間のハンドオフ、クラッシュリカバリ。

**Example:**
```python
# Source: stdlib dataclasses / json
import dataclasses
import json
from dataclasses import dataclass
from typing import Optional

@dataclass
class IssueContext:
    # --- Metadata (immutable after creation) ---
    issue_number: int
    issue_title: str
    started_at: str  # ISO 8601

    # --- Analyzer write zone ---
    issue_type: str = ""          # "bug" | "feature" | "refactor"
    affected_files: list = dataclasses.field(default_factory=list)  # max 15
    implementation_plan: str = ""
    complexity_score: float = 0.0  # 0-10

    # --- Specialist write zone ---
    changes_made: list = dataclasses.field(default_factory=list)
    tests_run: bool = False
    tests_passed: bool = False
    error_message: Optional[str] = None

    # --- Reviewer write zone ---
    review_passed: Optional[bool] = None  # None = abort扱い
    review_notes: str = ""
    security_issues: list = dataclasses.field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(dataclasses.asdict(self), ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, s: str) -> "IssueContext":
        return cls(**json.loads(s))
```

### Pattern 4: validate_pre_pr — 順序付き abort ゲート

**What:** 4条件を決定論的な順序でチェックし、最初の失敗で例外を raise する純粋関数。

**Example:**
```python
# Source: 設計決定 (CONTEXT.md)
import subprocess
import re

class ValidationError(Exception):
    """Pre-PR validation failure. Message is posted as Issue comment."""
    pass

def validate_pre_pr(ctx: "IssueContext", token_count: int = 0) -> None:
    # 1. affected_files 外変更検出
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True, text=True, check=True
    )
    changed = set(result.stdout.splitlines())
    allowed = set(ctx.affected_files)
    out_of_scope = changed - allowed
    if out_of_scope:
        raise ValidationError(f"Out-of-scope files modified: {sorted(out_of_scope)}")

    # 2. 既存テスト変更検出
    test_patterns = [re.compile(p) for p in [
        r"test_.*\.py$", r".*_test\.py$", r".*\.test\..*$", r"tests/"
    ]]
    for path in changed:
        if any(p.search(path) for p in test_patterns):
            raise ValidationError(f"Existing test file modified: {path}")

    # 3. セキュリティスキャン (Python のみ)
    import os
    is_python = os.path.exists("pyproject.toml") or os.path.exists("pytest.ini")
    if is_python:
        scan = subprocess.run(
            ["bandit", "-ll", "-r", "."],
            capture_output=True, text=True
        )
        if scan.returncode != 0:
            raise ValidationError(f"Bandit security scan failed:\n{scan.stdout}")

    # 4. トークン予算超過
    if token_count > 150_000:
        raise ValidationError(f"Token budget exceeded: {token_count} > 150,000")
```

### Pattern 5: AgentBase — ClaudeSDKClient ラッパー基底クラス

**What:** 共通 hooks + permission_mode + allowed_tools を保持する基底クラス。各エージェントが継承してオーバーライドする。

**Example:**
```python
# Source: client.py / types.py (SDK source inspection)
import asyncio
from claude_agent_sdk import (
    ClaudeSDKClient, ClaudeAgentOptions, HookMatcher,
    ResultMessage, TaskProgressMessage
)

class AgentBase:
    """Base class for all pipeline agents."""

    allowed_tools: list[str] = []

    def _make_options(self, extra_mcp_servers=None) -> ClaudeAgentOptions:
        return ClaudeAgentOptions(
            permission_mode="bypassPermissions",
            allowed_tools=self.allowed_tools,
            hooks={
                "SubagentStart": [HookMatcher(hooks=[self._on_subagent_start])],
                "SubagentStop":  [HookMatcher(hooks=[self._on_subagent_stop])],
            },
            mcp_servers=extra_mcp_servers or {},
        )

    async def _on_subagent_start(self, input, tool_use_id, context):
        print(f"[{self.__class__.__name__}] SubagentStart agent_id={input.get('agent_id')}")
        return {"continue_": True}

    async def _on_subagent_stop(self, input, tool_use_id, context):
        print(f"[{self.__class__.__name__}] SubagentStop agent_id={input.get('agent_id')}")
        return {"continue_": True}

    async def run(self, prompt: str) -> ResultMessage:
        options = self._make_options()
        async with ClaudeSDKClient(options) as client:
            await client.query(prompt)
            async for msg in client.receive_response():
                if isinstance(msg, ResultMessage):
                    return msg
        raise RuntimeError("No ResultMessage received")
```

### Pattern 6: token 累積カウントの取得

**What:** `TaskProgressMessage.usage.total_tokens` で逐次確認、または `ResultMessage.usage` でセッション終了後に取得。

```python
# Source: types.py — TaskProgressMessage, TaskUsage, ResultMessage
# TaskProgressMessage.usage は TaskUsage TypedDict: {"total_tokens": int, "tool_uses": int, "duration_ms": int}
# ResultMessage.usage は dict[str, Any] | None (raw)

cumulative_tokens = 0
async for msg in client.receive_messages():
    if isinstance(msg, TaskProgressMessage):
        cumulative_tokens = msg.usage["total_tokens"]
        if cumulative_tokens > 150_000:
            await client.interrupt()
    elif isinstance(msg, ResultMessage):
        break
```

### Anti-Patterns to Avoid

- **`shell=True` での subprocess 呼び出し:** shell injection のリスク。必ずリスト渡し + `shell=False`（デフォルト）を使う。
- **`frozen=True` の IssueContext:** 各ステージが書き込む必要があるため、frozen は使わない。
- **MCP ツールのハンドラで同期 subprocess.run を使う:** `@tool` ハンドラは async 関数だが、`subprocess.run` は同期。asyncio イベントループのブロッキングに注意。大量のツール呼び出しがある場合は `asyncio.to_thread(subprocess.run, ...)` を検討する（Phase 1 では単純実装で可）。
- **`HookEvent` 文字列のタイポ:** SDK は `"SubagentStart"` / `"SubagentStop"` の大文字小文字を厳密にチェックする（Literal 型定義済み）。
- **`@tool` デコレータの関数を直接呼び出し:** `@tool` で包んだ関数は `SdkMcpTool` オブジェクトになる。`tools=[list_open_issues]` と書くのが正しく、`tools=[list_open_issues.handler]` ではない。
- **`ResultMessage.usage` の型前提:** `dict[str, Any] | None` — None チェックが必要。

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| in-process MCP server | 手製の tool dispatcher | `create_sdk_mcp_server()` + `@tool` | SDK が MCP プロトコル全体を管理 |
| Python セキュリティスキャン | 自前の regex パターン集 | `bandit -ll` | edge case が膨大（eval, pickle, sql concat 等）|
| JSON スキーマ変換 | 手動 dict 構築 | `dataclasses.asdict()` + `json.dumps()` | ネストなしフラット構造なので stdlib で十分 |
| hook 登録 | 手製のイベントバス | `HookMatcher` + `ClaudeAgentOptions.hooks` | SDK が hook ルーティングを全管理 |

**Key insight:** SDK の `create_sdk_mcp_server` がツール登録・ルーティング・MCP プロトコル応答をすべて処理する。ツールハンドラは純粋な async 関数として実装するだけでよい。

---

## Common Pitfalls

### Pitfall 1: `@tool` ハンドラの戻り値フォーマット
**What goes wrong:** `return {"result": "..."}` と書いてしまい、Claude がツール結果を受け取れない。
**Why it happens:** MCP プロトコルは `{"content": [{"type": "text", "text": "..."}]}` 形式を要求する。
**How to avoid:** 必ず `{"content": [{"type": "text", "text": str(result)}]}` 形式で返す。エラー時は `{"content": [...], "is_error": True}`。
**Warning signs:** ツール呼び出しが成功するが Claude が空の結果を報告する。

### Pitfall 2: `list` フィールドのデフォルト値
**What goes wrong:** `affected_files: list[str] = []` と書くと `ValueError: mutable default is not allowed` が出る。
**Why it happens:** dataclass はミュータブルなデフォルト値を禁止する。
**How to avoid:** `affected_files: list = dataclasses.field(default_factory=list)` を使う。
**Warning signs:** `dataclass` 定義時に即座に ValueError。

### Pitfall 3: `from_json()` でのフィールド不整合
**What goes wrong:** JSON に存在しないフィールドや余分なフィールドがあると `TypeError: __init__() got an unexpected keyword argument` が出る。
**Why it happens:** `cls(**json.loads(s))` は JSON のキーをそのままコンストラクタ引数に渡す。
**How to avoid:** `from_json()` で既知フィールド以外を無視するか、バリデーションを追加する。または dataclass のフィールド名を変更しない（後方互換性の確保）。
**Warning signs:** クラッシュリカバリ時の再開失敗。

### Pitfall 4: subprocess.run の check=True と例外伝播
**What goes wrong:** `gh` CLI が non-zero で終了したとき、`check=False`（デフォルト）だと例外が起きず失敗が無視される。
**Why it happens:** デフォルトは `check=False`。
**How to avoid:** `subprocess.run(..., check=True)` を使い、`CalledProcessError` を上位でキャッチして `agent-failed` ラベル付与につなげる。
**Warning signs:** ツールが成功したように見えるが GitHub に変更が反映されない。

### Pitfall 5: `HookMatcher.matcher` の省略
**What goes wrong:** `HookMatcher(hooks=[fn])` で `matcher=None` のままにしておくと、すべてのイベントでフックが呼ばれることを前提にしている。`SubagentStart` / `SubagentStop` はツール名ではなくイベント名なので matcher は None で正しい。
**Why it happens:** `PreToolUse` などはツール名で絞り込めるが、`SubagentStart/Stop` にはツールコンテキストがない。
**How to avoid:** `SubagentStart` / `SubagentStop` フックには `matcher=None` で問題なし。
**Warning signs:** 誤ったツール名を matcher に指定してフックが呼ばれない。

### Pitfall 6: bandit の終了コード解釈
**What goes wrong:** `bandit` はデフォルトで警告があっても終了コード 0 を返すケースがある。`-ll` (MEDIUM以上) フラグと組み合わせた場合の動作を誤解する。
**Why it happens:** bandit の終了コードはバージョンと設定に依存する。
**How to avoid:** `returncode != 0` だけでなく、stdout に "Issue:" または "Severity:" が含まれるかも確認する。または bandit の `-o` オプションで JSON 出力し、`results` 配列の length を確認する。
**Warning signs:** セキュリティ問題があっても validate_pre_pr が通過してしまう。

### Pitfall 7: `ClaudeAgentOptions.allowed_tools` の命名ルール
**What goes wrong:** SDK MCP ツールの名前（`@tool("list_open_issues", ...)`）と `allowed_tools` リストの名前が一致しないとツールが呼ばれない。
**Why it happens:** `allowed_tools` はツール名の文字列リスト。MCP ツール名と完全一致が必要。
**How to avoid:** ツール名を定数として定義し、両方から参照する。
**Warning signs:** Claude がツールを使わずに答えを作ろうとする。

---

## Code Examples

Verified patterns from SDK source inspection:

### ClaudeAgentOptions の完全な初期化パターン
```python
# Source: types.py (ClaudeAgentOptions dataclass, line 1042+)
from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, AgentDefinition

options = ClaudeAgentOptions(
    permission_mode="bypassPermissions",    # PermissionMode Literal
    allowed_tools=["list_open_issues", "claim_issue", "Bash", "Read"],
    mcp_servers={"github": github_server_config},  # McpSdkServerConfig
    hooks={
        "SubagentStart": [HookMatcher(matcher=None, hooks=[on_start_fn])],
        "SubagentStop":  [HookMatcher(matcher=None, hooks=[on_stop_fn])],
    },
    agents={
        "analyzer": AgentDefinition(
            description="Analyzes GitHub issues",
            prompt="You are an analyzer...",
            tools=["Read", "Grep", "Glob"],
            model="inherit",
        )
    },
    max_turns=5,
)
```

### ClaudeSDKClient の async context manager 使用パターン
```python
# Source: client.py (__aenter__ / __aexit__ / receive_response)
import asyncio
from claude_agent_sdk import ClaudeSDKClient, ResultMessage

async def run_agent(prompt: str, options: ClaudeAgentOptions) -> ResultMessage:
    async with ClaudeSDKClient(options) as client:
        await client.query(prompt)
        async for msg in client.receive_response():
            if isinstance(msg, ResultMessage):
                return msg
    raise RuntimeError("No ResultMessage")

# 同期コンテキストから呼ぶ場合
result = asyncio.run(run_agent("...prompt...", options))
```

### gh CLI による Issue ラベル操作
```python
# Source: 設計決定 (CONTEXT.md) — shell=False, list 渡し
import subprocess
import json

def claim_issue_impl(issue_number: int) -> None:
    """Add agent-processing label to issue."""
    subprocess.run(
        ["gh", "issue", "edit", str(issue_number),
         "--add-label", "agent-processing"],
        check=True, capture_output=True, text=True
    )

def release_issue_impl(issue_number: int, outcome: str) -> None:
    """Remove agent-processing and add outcome label."""
    label_map = {
        "resolved": "agent-resolved",
        "skip":     "agent-skip",
        "failed":   "agent-failed",
    }
    outcome_label = label_map[outcome]
    subprocess.run(
        ["gh", "issue", "edit", str(issue_number),
         "--remove-label", "agent-processing",
         "--add-label", outcome_label],
        check=True, capture_output=True, text=True
    )
```

### main.py の差し替えパターン
```python
# Source: 設計決定 (CONTEXT.md / STATE.md) — query() → ClaudeSDKClient
# 現在の main.py: from claude_agent_sdk import query  →  削除
# 新しい main.py:
import asyncio
from issue_resolver.run import run_pipeline

def main():
    asyncio.run(run_pipeline())

if __name__ == "__main__":
    main()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `query()` 関数 | `ClaudeSDKClient` | SDK 設計時から | `agents` dict は ClaudeSDKClient の streaming-mode initialize handshake でのみ送信される |
| 外部 MCP サーバー（subprocess） | `create_sdk_mcp_server()` in-process | SDK v0.1.50 | IPC オーバーヘッドなし、デバッグが容易 |
| `permissionMode: "acceptEdits"` | `permission_mode="bypassPermissions"` + `allowed_tools` | SDK 設計 | 自律動作には bypassPermissions が必須 |

**Deprecated/outdated:**
- `query()` 関数: 自律マルチエージェントには使わない（AgentDefinition を無視する）。`ClaudeSDKClient` を使う。
- `max_thinking_tokens`: deprecated、代わりに `thinking` パラメータを使う（Phase 1 では使わない）。

---

## Open Questions

1. **bandit の終了コード信頼性**
   - What we know: `bandit -ll` は MEDIUM 以上の問題を検出するが、問題がある場合の終了コードはバージョン依存
   - What's unclear: GitHub Actions の ubuntu-latest に bandit が入っているか、また `returncode != 0` が十分な判定条件か
   - Recommendation: `uv add bandit` で依存追加 + JSON 出力モード (`bandit -ll -f json`) で `results` 配列の長さをチェックする。`returncode` は補助的に使う。

2. **`gh` CLI の GITHUB_TOKEN 環境変数**
   - What we know: `gh` は `GH_TOKEN` または `GITHUB_TOKEN` 環境変数を使用する
   - What's unclear: GitHub Actions 外のローカル開発時の認証状態
   - Recommendation: Phase 1 UAT は実際の GitHub リポジトリに対して行う前提（CONTEXT.md 確認済み）。ローカルでは `gh auth login` 済み前提とする。

3. **`asyncio.run()` vs `anyio.run()` の選択**
   - What we know: SDK 内部は `anyio` を使用（`client.py` の import から確認済み）
   - What's unclear: `asyncio.run()` で呼んだ場合に内部の `anyio` タスクグループが正しく動作するか
   - Recommendation: SDK のドキュメントに `asyncio.run()` 使用例が多数あるため問題ない可能性が高い。Phase 1 の統合テストで確認する。

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (検出: pyproject.toml に pytest がまだ追加されていないが、Python プロジェクト標準) |
| Config file | なし — Wave 0 で作成 |
| Quick run command | `uv run pytest tests/ -x -q` |
| Full suite command | `uv run pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UAT-1 | `list_open_issues()` が open な未処理 Issue を返す | integration | `uv run pytest tests/test_github_tools.py::test_list_open_issues -x` | ❌ Wave 0 |
| UAT-2 | `claim_issue()` でラベルが付与され、次の `list_open_issues()` でスキップされる | integration | `uv run pytest tests/test_github_tools.py::test_claim_and_skip -x` | ❌ Wave 0 |
| UAT-3 | `IssueContext` が JSON にシリアライズ/デシリアライズできる | unit | `uv run pytest tests/test_context.py::test_issue_context_json_roundtrip -x` | ❌ Wave 0 |
| UAT-4a | affected_files 外変更検出が abort する | unit | `uv run pytest tests/test_validation.py::test_out_of_scope_abort -x` | ❌ Wave 0 |
| UAT-4b | 既存テスト変更検出が abort する | unit | `uv run pytest tests/test_validation.py::test_test_file_modification_abort -x` | ❌ Wave 0 |
| UAT-4c | セキュリティスキャン失敗が abort する | unit | `uv run pytest tests/test_validation.py::test_security_scan_abort -x` | ❌ Wave 0 |
| UAT-4d | トークン予算超過が abort する | unit | `uv run pytest tests/test_validation.py::test_token_budget_abort -x` | ❌ Wave 0 |

注意: UAT-1, UAT-2 は実際の GitHub リポジトリに対する統合テスト。ローカル単体テストでは `subprocess.run` をモックする。

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_context.py tests/test_validation.py -x -q`
- **Per wave merge:** `uv run pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/__init__.py` — テストパッケージ初期化
- [ ] `tests/test_context.py` — IssueContext の JSON ラウンドトリップ、フィールドデフォルト値
- [ ] `tests/test_validation.py` — 4条件の独立テスト（subprocess.run モック使用）
- [ ] `tests/test_github_tools.py` — list_open_issues/claim_issue の単体テスト（gh CLI モック）
- [ ] `pyproject.toml` への pytest 追加: `uv add --dev pytest`
- [ ] `issue-resolver/` ディレクトリ作成と `__init__.py`

---

## Sources

### Primary (HIGH confidence)
- SDK ソースコード `/home/utakata/ドキュメント/utakata-agent/.venv/lib/python3.12/site-packages/claude_agent_sdk/` — `__init__.py` (tool, create_sdk_mcp_server), `client.py` (ClaudeSDKClient), `types.py` (ClaudeAgentOptions, HookEvent, AgentDefinition, SubagentStartHookInput, ResultMessage, TaskProgressMessage)
- `.planning/phases/01-pipeline-skeleton-safety/01-CONTEXT.md` — 全設計決定
- `.planning/research/SUMMARY.md` — プロジェクト全体の研究結果（SDK・アーキテクチャ）

### Secondary (MEDIUM confidence)
- Python 標準ライブラリ `dataclasses` / `json` / `subprocess` ドキュメント（安定 API）
- `gh` CLI の `issue edit --add-label` / `--remove-label` コマンド（stable since 2021）

### Tertiary (LOW confidence)
- `bandit -ll` の終了コード信頼性 — バージョン依存のため要検証
- `asyncio.run()` + anyio 内部の互換性 — Phase 1 統合テストで確認が必要

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — SDK ソースコードを直接確認。stdlib は安定。
- Architecture: HIGH — CONTEXT.md の設計決定が詳細で確定済み。SDK の型定義と一致する。
- Pitfalls: HIGH (MCP/SDK関連) / MEDIUM (bandit終了コード) — SDK ソース確認済み。bandit のみ外部依存。

**Research date:** 2026-03-22
**Valid until:** 2026-04-22（claude-agent-sdk が 0.2.x にメジャーアップグレードされた場合は再調査）
