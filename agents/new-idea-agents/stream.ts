import type { SDKMessage } from "@anthropic-ai/claude-agent-sdk";

/**
 * query() が返す AsyncGenerator<SDKMessage> を受け取り、
 * assistant メッセージのテキストを stdout にストリーミング出力する。
 * エラー結果の場合は stderr に書いてエラーをスローする。
 */
export async function streamOutput(
  messages: AsyncIterable<SDKMessage>,
): Promise<void> {
  for await (const message of messages) {
    if (message.type === "assistant") {
      for (const block of message.message.content) {
        if (block.type === "text") {
          process.stdout.write(block.text);
        }
      }
    } else if (message.type === "result") {
      if (message.subtype !== "success") {
        const errors =
          "errors" in message && Array.isArray(message.errors)
            ? message.errors.join(", ")
            : "Unknown error";
        process.stderr.write(`\nError: ${errors}\n`);
        throw new Error(`Agent failed: ${errors}`);
      }
    }
    // system, status, tool_progress など他のメッセージは無視
  }
  process.stdout.write("\n");
}
