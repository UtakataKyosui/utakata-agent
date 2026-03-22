import yargs from "yargs";
import { hideBin } from "yargs/helpers";
import { join } from "node:path";
import { homedir } from "node:os";
import { query } from "@anthropic-ai/claude-agent-sdk";
import { discoverAgents, buildPrompt, type AgentConfig } from "./loader";
import { streamOutput } from "./stream";

// ─── エージェント実行 ─────────────────────────────────────────────────

async function runAgent(config: AgentConfig, argv: Record<string, unknown>): Promise<void> {
  const prompt = buildPrompt(config, argv);

  const q = query({
    prompt,
    options: {
      cwd: config.hasCwd ? String(argv["cwd"] ?? process.cwd()) : undefined,
      permissionMode: config.permissionMode ?? "default",
      ...(config.tools ? { allowedTools: config.tools } : {}),
      ...(config.subagents ? { agents: config.subagents } : {}),
    },
  });

  try {
    await streamOutput(q);
  } catch {
    process.exit(1);
  }
}

// ─── CLI コマンド署名を組み立てる ────────────────────────────────────

function buildCommandSignature(name: string, config: AgentConfig): string {
  const positionals = config.args?.filter((a) => a.positional) ?? [];
  const parts = [name];
  for (const arg of positionals) {
    parts.push(arg.required ? `<${arg.name}>` : `[${arg.name}]`);
  }
  return parts.join(" ");
}

// ─── yargs にオプション引数を登録する ────────────────────────────────

function registerArgs(y: ReturnType<typeof yargs>, config: AgentConfig): ReturnType<typeof yargs> {
  for (const arg of config.args ?? []) {
    if (arg.positional) {
      y.positional(arg.name, {
        describe: arg.description ?? "",
        type: (arg.type as "string" | "number" | "boolean" | undefined) ?? "string",
        demandOption: arg.required ?? false,
      });
    } else {
      y.option(arg.name, {
        describe: arg.description ?? "",
        type: (arg.type as "string" | "number" | "boolean" | undefined) ?? "string",
      });
    }
  }

  if (config.hasCwd) {
    y.option("cwd", {
      describe: "リポジトリのパス（デフォルト: カレントディレクトリ）",
      type: "string",
      default: process.cwd(),
    });
  }

  return y;
}

// ─── エントリポイント ─────────────────────────────────────────────────

async function main() {
  const searchPaths = [
    join(import.meta.dir, "agents"),
    join(process.cwd(), ".claude", "agents"),
    join(homedir(), ".claude", "agents"),
  ];

  const agents = await discoverAgents(searchPaths);

  const cli = yargs(hideBin(process.argv))
    .scriptName("agent")
    .usage("$0 <command> [options]")
    .example('$0 ask "TypeScriptとは？"', "ワンショット質問")
    .example('$0 meal "夕食" --constraint "糖質制限"', "食事提案")
    .example("$0 issue https://github.com/org/repo/issues/1 --cwd ./repo", "Issue解決")
    .example("$0 review https://github.com/org/repo/pull/42", "PRレビュー")
    .strict()
    .wrap(null);

  for (const [name, config] of agents) {
    const signature = buildCommandSignature(name, config);
    cli.command(
      signature,
      config.description,
      (y) => registerArgs(y as ReturnType<typeof yargs>, config),
      (argv) => runAgent(config, argv as Record<string, unknown>),
    );
  }

  await cli.demandCommand(1, "コマンドを指定してください。").help().parseAsync();
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
