import { test, expect, describe } from "bun:test";
import { parseAgentFile, buildPrompt } from "./loader";

// ─── parseAgentFile のテスト ───────────────────────────────────────────

describe("parseAgentFile", () => {
  test("name と description をフロントマターから読み取る", () => {
    const md = `---
name: ask
description: ワンショット質問エージェント
---
あなたは親切なアシスタントです。
`;
    const config = parseAgentFile(md);
    expect(config.name).toBe("ask");
    expect(config.description).toBe("ワンショット質問エージェント");
  });

  test("systemPrompt はフロントマター以外の部分", () => {
    const md = `---
name: chat
description: 汎用チャット
---
システムプロンプト本文。
複数行。
`;
    const config = parseAgentFile(md);
    expect(config.systemPrompt.trim()).toBe("システムプロンプト本文。\n複数行。");
  });

  test("tools を配列で読み取る", () => {
    const md = `---
name: issue
description: Issue解決
tools:
  - Read
  - Write
  - Bash
---
プロンプト
`;
    const config = parseAgentFile(md);
    expect(config.tools).toEqual(["Read", "Write", "Bash"]);
  });

  test("permissionMode を読み取る", () => {
    const md = `---
name: issue
description: Issue解決
permissionMode: acceptEdits
---
プロンプト
`;
    const config = parseAgentFile(md);
    expect(config.permissionMode).toBe("acceptEdits");
  });

  test("permissionMode がなければ undefined", () => {
    const md = `---
name: ask
description: 質問
---
プロンプト
`;
    const config = parseAgentFile(md);
    expect(config.permissionMode).toBeUndefined();
  });

  test("cwd: true で hasCwd が true になる", () => {
    const md = `---
name: issue
description: Issue解決
cwd: true
---
プロンプト
`;
    const config = parseAgentFile(md);
    expect(config.hasCwd).toBe(true);
  });

  test("args の positional 引数を読み取る", () => {
    const md = `---
name: issue
description: Issue解決
args:
  - name: url
    description: Issue URL
    required: true
    positional: true
---
プロンプト
`;
    const config = parseAgentFile(md);
    expect(config.args).toHaveLength(1);
    expect(config.args![0]).toMatchObject({
      name: "url",
      description: "Issue URL",
      required: true,
      positional: true,
    });
  });

  test("SubAgents セクションをパースして subagents に格納する", () => {
    const md = `---
name: issue
description: Issue解決
subagents:
  - code-analyzer
---
メインプロンプト

## SubAgents

### code-analyzer
> description: コードを解析する
> tools: Read, Grep

コードを読み込んでください。
`;
    const config = parseAgentFile(md);
    expect(config.subagents).toBeDefined();
    expect(config.subagents!["code-analyzer"]).toMatchObject({
      description: "コードを解析する",
    });
    expect(config.subagents!["code-analyzer"].tools).toContain("Read");
    expect(config.subagents!["code-analyzer"].tools).toContain("Grep");
    expect(config.subagents!["code-analyzer"].prompt).toContain("コードを読み込んでください。");
  });

  test("SubAgents セクションがなければ subagents は undefined", () => {
    const md = `---
name: ask
description: 質問
---
プロンプト
`;
    const config = parseAgentFile(md);
    expect(config.subagents).toBeUndefined();
  });
});

// ─── buildPrompt のテスト ─────────────────────────────────────────────

describe("buildPrompt", () => {
  test("{{変数名}} をargvの値で展開する", () => {
    const md = `---
name: issue
description: Issue解決
args:
  - name: url
    positional: true
---
以下のIssueを解決してください: {{url}}
`;
    const config = parseAgentFile(md);
    const prompt = buildPrompt(config, { url: "https://github.com/owner/repo/issues/1" });
    expect(prompt).toContain("https://github.com/owner/repo/issues/1");
    expect(prompt).not.toContain("{{url}}");
  });

  test("変数がなければシステムプロンプトをそのまま返す", () => {
    const md = `---
name: ask
description: 質問
---
あなたは質問に答えます。
`;
    const config = parseAgentFile(md);
    const prompt = buildPrompt(config, { question: "テスト" });
    expect(prompt).toBe("あなたは質問に答えます。\n\n質問: テスト");
  });

  test("ask コマンドは question をプロンプトの末尾に追加する", () => {
    const md = `---
name: ask
description: 質問
---
あなたは質問に答えます。
`;
    const config = parseAgentFile(md);
    const prompt = buildPrompt(config, { question: "Bunとは？" });
    expect(prompt).toContain("Bunとは？");
  });
});
