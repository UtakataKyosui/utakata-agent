import { readdir, readFile } from "node:fs/promises";
import { join, basename, extname } from "node:path";
import { homedir } from "node:os";
import type { AgentDefinition } from "@anthropic-ai/claude-agent-sdk";

export type PermissionMode = "default" | "acceptEdits" | "bypassPermissions" | "plan" | "dontAsk";

export type ArgDefinition = {
  name: string;
  description?: string;
  required?: boolean;
  positional?: boolean;
  type?: "string" | "number" | "boolean";
};

export type AgentConfig = {
  name: string;
  description: string;
  tools?: string[];
  permissionMode?: PermissionMode;
  hasCwd?: boolean;
  args?: ArgDefinition[];
  systemPrompt: string;
  subagents?: Record<string, AgentDefinition>;
};

// ─── YAML フロントマターの簡易パーサー ────────────────────────────────

type FrontMatter = {
  name?: string;
  description?: string;
  tools?: string[];
  permissionMode?: string;
  cwd?: boolean;
  args?: ArgDefinition[];
  subagents?: string[];
};

/**
 * `---\n...\n---` 形式のフロントマターをパースする。
 * 依存を増やさないため、最低限の YAML サブセットのみ対応。
 */
function scalarValue(v: string): string | boolean {
  return v === "true" ? true : v === "false" ? false : v;
}

function parseFrontMatter(text: string): FrontMatter {
  const result: FrontMatter = {};
  const lines = text.split("\n");
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim() || line.trim().startsWith("#")) {
      i++;
      continue;
    }

    const colonIdx = line.indexOf(":");
    if (colonIdx === -1) {
      i++;
      continue;
    }

    const key = line.slice(0, colonIdx).trim();
    const value = line.slice(colonIdx + 1).trim();

    if (value !== "") {
      // スカラー値
      (result as Record<string, unknown>)[key] = scalarValue(value);
      i++;
      continue;
    }

    // 値が空 → 配列またはオブジェクト配列
    i++;
    const items: Array<string | Record<string, unknown>> = [];

    while (i < lines.length) {
      const itemLine = lines[i];
      if (!itemLine.startsWith("  ") && !itemLine.startsWith("\t")) break;

      const trimmed = itemLine.trim();
      if (trimmed.startsWith("- ")) {
        const rest = trimmed.slice(2).trim();
        const ci = rest.indexOf(":");
        if (ci !== -1) {
          // オブジェクト配列の先頭フィールド: `- key: value`
          const obj: Record<string, unknown> = {};
          const k = rest.slice(0, ci).trim();
          const v = rest.slice(ci + 1).trim();
          obj[k] = scalarValue(v);
          i++;
          // 続くインデント（4スペース）のフィールドを読む
          while (i < lines.length) {
            const nextLine = lines[i];
            if (!nextLine.startsWith("    ") && !nextLine.startsWith("\t\t")) break;
            const nextTrimmed = nextLine.trim();
            if (nextTrimmed.startsWith("- ")) break;
            const nci = nextTrimmed.indexOf(":");
            if (nci !== -1) {
              const nk = nextTrimmed.slice(0, nci).trim();
              const nv = nextTrimmed.slice(nci + 1).trim();
              obj[nk] = scalarValue(nv);
            }
            i++;
          }
          items.push(obj);
        } else {
          // 単純な文字列配列: `- value`
          items.push(rest);
          i++;
        }
      } else {
        i++;
      }
    }

    (result as Record<string, unknown>)[key] = items;
  }

  return result;
}

// ─── SubAgents セクションのパーサー ─────────────────────────────────

/**
 * `## SubAgents` セクションから SubAgent 定義を抽出する。
 *
 * 形式:
 * ```
 * ## SubAgents
 *
 * ### <name>
 * > description: ...
 * > tools: Tool1, Tool2
 *
 * システムプロンプト本文
 * ```
 */
function parseSubAgents(body: string): Record<string, AgentDefinition> | undefined {
  const subAgentSectionMatch = body.match(/^## SubAgents\s*\n([\s\S]*)/m);
  if (!subAgentSectionMatch) return undefined;

  const section = subAgentSectionMatch[1];
  const agentBlocks = section.split(/^### /m).filter(Boolean);
  if (agentBlocks.length === 0) return undefined;

  const result: Record<string, AgentDefinition> = {};

  for (const block of agentBlocks) {
    const lines = block.split("\n");
    const name = lines[0].trim();
    if (!name) continue;

    let description = "";
    let tools: string[] | undefined;
    const promptLines: string[] = [];
    let inMeta = true;

    for (let i = 1; i < lines.length; i++) {
      const line = lines[i];
      if (inMeta && line.trim().startsWith(">")) {
        const metaLine = line.trim().slice(1).trim();
        const ci = metaLine.indexOf(":");
        if (ci !== -1) {
          const k = metaLine.slice(0, ci).trim();
          const v = metaLine.slice(ci + 1).trim();
          if (k === "description") description = v;
          else if (k === "tools")
            tools = v
              .split(",")
              .map((t) => t.trim())
              .filter(Boolean);
        }
      } else {
        inMeta = false;
        promptLines.push(line);
      }
    }

    const prompt = promptLines.join("\n").trim();
    result[name] = { description, prompt, ...(tools ? { tools } : {}) };
  }

  return Object.keys(result).length > 0 ? result : undefined;
}

// ─── メイン公開 API ──────────────────────────────────────────────────

/**
 * .md ファイルの文字列をパースして AgentConfig を返す。
 */
export function parseAgentFile(content: string): AgentConfig {
  const fmMatch = content.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!fmMatch) {
    throw new Error("エージェントファイルにフロントマターが見つかりません");
  }

  const fm = parseFrontMatter(fmMatch[1]);
  const body = fmMatch[2];

  // SubAgents セクションを除いた本文をシステムプロンプトとして使用
  const systemPrompt = body.replace(/^## SubAgents[\s\S]*$/m, "").trim();

  const subagents = parseSubAgents(body);

  return {
    name: fm.name ?? "",
    description: fm.description ?? "",
    ...(fm.tools && fm.tools.length > 0 ? { tools: fm.tools as string[] } : {}),
    ...(fm.permissionMode ? { permissionMode: fm.permissionMode as PermissionMode } : {}),
    ...(fm.cwd ? { hasCwd: true } : {}),
    ...(fm.args && fm.args.length > 0 ? { args: fm.args as ArgDefinition[] } : {}),
    systemPrompt,
    ...(subagents ? { subagents } : {}),
  };
}

/**
 * AgentConfig とコマンドライン引数から実際のプロンプト文字列を組み立てる。
 * - `{{変数名}}` をargvの対応する値で展開する
 * - `ask` コマンドなど positional な引数を持たない場合は末尾に追加する
 */
export function buildPrompt(config: AgentConfig, argv: Record<string, unknown>): string {
  let prompt = config.systemPrompt;

  // テンプレート変数を展開
  let hasTemplate = false;
  for (const [key, value] of Object.entries(argv)) {
    if (key === "_" || key === "$0") continue;
    const placeholder = `{{${key}}}`;
    if (prompt.includes(placeholder)) {
      prompt = prompt.replaceAll(placeholder, String(value));
      hasTemplate = true;
    }
  }

  // テンプレート変数がなかった場合（ask/chat など）は末尾にユーザー入力を追加
  if (!hasTemplate) {
    // positional な引数の値を末尾に付加
    const positionalArgs = config.args?.filter((a) => a.positional) ?? [];
    const extras: string[] = [];

    if (positionalArgs.length > 0) {
      for (const arg of positionalArgs) {
        if (argv[arg.name] !== undefined) {
          extras.push(`${arg.name === "question" ? "質問" : arg.name}: ${argv[arg.name]}`);
        }
      }
    } else {
      // ask コマンドなど: positional 定義なしで question キーを探す
      const q = argv.question ?? argv.prompt ?? argv._?.[0];
      if (q !== undefined) extras.push(`質問: ${q}`);
    }

    if (extras.length > 0) {
      prompt = `${prompt}\n\n${extras.join("\n")}`;
    }
  }

  return prompt;
}

// ─── エージェント検出 ────────────────────────────────────────────────

/**
 * 指定されたパスから .md ファイルを読み込み、AgentConfig の Map を返す。
 * 後のパスが同名エージェントを上書きする（ユーザー定義が組み込みを上書き）。
 */
export async function discoverAgents(searchPaths: string[]): Promise<Map<string, AgentConfig>> {
  const result = new Map<string, AgentConfig>();

  for (const dirPath of searchPaths) {
    let entries: string[];
    try {
      entries = await readdir(dirPath);
    } catch {
      continue; // ディレクトリが存在しない場合はスキップ
    }

    for (const entry of entries) {
      if (!entry.endsWith(".md")) continue;
      const filePath = join(dirPath, entry);
      try {
        const content = await readFile(filePath, "utf-8");
        const config = parseAgentFile(content);
        const name = config.name || basename(entry, extname(entry));
        result.set(name, { ...config, name });
      } catch (err) {
        console.warn(`エージェントファイルの読み込みに失敗: ${filePath}: ${err}`);
      }
    }
  }

  return result;
}

/**
 * デフォルトのエージェント検索パス一覧を返す。
 */
export function defaultSearchPaths(projectRoot: string): string[] {
  return [
    join(import.meta.dir, "agents"), // 組み込み
    join(projectRoot, ".claude", "agents"), // プロジェクトレベル
    join(homedir(), ".claude", "agents"), // ユーザーレベル
  ];
}
