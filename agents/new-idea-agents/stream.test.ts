import { test, expect, spyOn, afterEach } from "bun:test";
import { streamOutput } from "./stream";
import type { SDKMessage } from "@anthropic-ai/claude-agent-sdk";

// テスト用の AsyncGenerator を作るヘルパー
async function* makeMessages(...messages: SDKMessage[]) {
  for (const msg of messages) {
    yield msg;
  }
}

function makeAssistantMessage(text: string): SDKMessage {
  return {
    type: "assistant",
    message: {
      id: "msg_test",
      type: "message",
      role: "assistant",
      model: "claude-sonnet-4-6",
      stop_reason: "end_turn",
      stop_sequence: null,
      usage: { input_tokens: 0, output_tokens: 0, cache_creation_input_tokens: 0, cache_read_input_tokens: 0 },
      content: [{ type: "text", text }],
    },
  } as SDKMessage;
}

function makeResultMessage(success: true): SDKMessage;
function makeResultMessage(success: false, error: string): SDKMessage;
function makeResultMessage(success: boolean, error?: string): SDKMessage {
  if (success) {
    return {
      type: "result",
      subtype: "success",
      result: "done",
      session_id: "sess_test",
      total_cost_usd: 0,
      duration_ms: 0,
      duration_api_ms: 0,
      is_error: false,
      num_turns: 1,
    } as SDKMessage;
  }
  return {
    type: "result",
    subtype: "error_during_execution",
    error: error!,
    session_id: "sess_test",
    total_cost_usd: 0,
    duration_ms: 0,
    duration_api_ms: 0,
    is_error: true,
    num_turns: 1,
  } as SDKMessage;
}

afterEach(() => {
  // spyOn で上書きしたものを戻す（restore は自動で行われる）
});

test("assistant メッセージのテキストを stdout に書き込む", async () => {
  const written: string[] = [];
  const spy = spyOn(process.stdout, "write").mockImplementation((s) => {
    written.push(String(s));
    return true;
  });

  await streamOutput(makeMessages(makeAssistantMessage("hello world")));

  expect(written).toContain("hello world");
  spy.mockRestore();
});

test("複数の assistant メッセージを順番に出力する", async () => {
  const written: string[] = [];
  const spy = spyOn(process.stdout, "write").mockImplementation((s) => {
    written.push(String(s));
    return true;
  });

  await streamOutput(
    makeMessages(
      makeAssistantMessage("first"),
      makeAssistantMessage("second"),
    ),
  );

  expect(written.join("")).toContain("first");
  expect(written.join("")).toContain("second");
  spy.mockRestore();
});

test("result success のとき改行を出力して正常終了する", async () => {
  const written: string[] = [];
  const spy = spyOn(process.stdout, "write").mockImplementation((s) => {
    written.push(String(s));
    return true;
  });

  await streamOutput(makeMessages(makeResultMessage(true)));

  expect(written).toContain("\n");
  spy.mockRestore();
});

test("system メッセージは無視する（stdout に書かない）", async () => {
  const written: string[] = [];
  const spy = spyOn(process.stdout, "write").mockImplementation((s) => {
    written.push(String(s));
    return true;
  });

  const systemMsg = { type: "system", subtype: "init" } as unknown as SDKMessage;
  await streamOutput(makeMessages(systemMsg, makeResultMessage(true)));

  // system メッセージ由来のテキストは含まれない（改行のみ）
  expect(written.filter((s) => s !== "\n")).toHaveLength(0);
  spy.mockRestore();
});
