#!/usr/bin/env node
/**
 * Lemove Code — servidor MCP v0.3.0
 *
 * Tools disponíveis:
 *  Projeto:    set_project, get_project
 *  Arquivos:   read_file, write_file, edit_file, create_directory,
 *              delete_file, move_file, copy_file, get_file_info
 *  Navegação:  list_dir, list_dir_recursive, find_files, search_in_files
 *  Git:        git_status, git_diff, git_log, git_add, git_commit,
 *              git_branch, git_checkout
 *  Terminal:   run_bash
 *  Resposta:   (write_file + signal automático para a TUI)
 */

const { Server } = require("@modelcontextprotocol/sdk/server/index.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} = require("@modelcontextprotocol/sdk/types.js");

const fs   = require("fs");
const path = require("path");
const os   = require("os");
const { execSync, spawnSync } = require("child_process");

// ── Projeto ativo ─────────────────────────────────────────────────────────
let activeProject = path.resolve(
  process.argv[2] || process.env.LEMOVE_BASE_DIR || os.homedir()
);

function resolveInProject(userPath) {
  if (!userPath || userPath === ".") return activeProject;
  return path.isAbsolute(userPath)
    ? path.normalize(userPath)
    : path.resolve(activeProject, userPath);
}

// ── Visual helpers ─────────────────────────────────────────────────────────
function box(title, bodyLines) {
  const width = Math.max(title.length + 4, ...bodyLines.map((l) => l.length + 2), 28);
  const top    = `╭─ ${title} ${"─".repeat(Math.max(0, width - title.length - 4))}╮`;
  const bottom = `╰${"─".repeat(width)}╯`;
  const body   = bodyLines
    .map((l) => `│ ${l}${" ".repeat(Math.max(0, width - l.length - 1))}│`)
    .join("\n");
  return `${top}\n${body}\n${bottom}`;
}

function shortPath(p) {
  return p.replace(os.homedir(), "~");
}

function prompt() {
  return `➜ ${shortPath(activeProject)}`;
}

function terminalBlock(command, output) {
  return "```\n" + `${prompt()} ${command}\n${output}` + "\n```";
}

function sizeHuman(bytes) {
  if (bytes < 1024)       return `${bytes} B`;
  if (bytes < 1048576)    return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1048576).toFixed(1)} MB`;
}

// ── Definição das ferramentas ──────────────────────────────────────────────
const TOOLS = [
  // ── Projeto ────────────────────────────────────────────────────────────
  {
    name: "set_project",
    description:
      "Define a pasta de projeto ativa. Todas as outras ferramentas (read_file, write_file, run_bash, etc.) passam a operar a partir dela quando você usar caminhos relativos. Use isso primeiro, no início da conversa, tipo 'abrir esse projeto'.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Caminho completo da pasta do projeto" },
      },
      required: ["path"],
    },
  },
  {
    name: "get_project",
    description: "Mostra qual é a pasta de projeto ativa no momento.",
    inputSchema: { type: "object", properties: {} },
  },

  // ── Arquivos ───────────────────────────────────────────────────────────
  {
    name: "read_file",
    description:
      "Lê o conteúdo de um arquivo de texto. Caminho relativo é resolvido a partir do projeto ativo; também aceita caminho absoluto.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Caminho do arquivo (relativo ao projeto ativo, ou absoluto)" },
        start_line: { type: "number", description: "Linha inicial (1-indexed, opcional)" },
        end_line:   { type: "number", description: "Linha final inclusive (opcional)" },
      },
      required: ["path"],
    },
  },
  {
    name: "write_file",
    description: "Cria um novo arquivo ou sobrescreve completamente um arquivo existente.",
    inputSchema: {
      type: "object",
      properties: {
        path:    { type: "string", description: "Caminho do arquivo (relativo ao projeto ativo, ou absoluto)" },
        content: { type: "string", description: "Conteúdo completo do arquivo" },
      },
      required: ["path", "content"],
    },
  },
  {
    name: "edit_file",
    description:
      "Substitui um trecho exato de texto por outro dentro de um arquivo. old_str precisa aparecer exatamente uma vez.",
    inputSchema: {
      type: "object",
      properties: {
        path:    { type: "string", description: "Caminho do arquivo (relativo ao projeto ativo, ou absoluto)" },
        old_str: { type: "string", description: "Texto exato a ser substituído (deve ser único no arquivo)" },
        new_str: { type: "string", description: "Texto que vai substituir old_str" },
      },
      required: ["path", "old_str", "new_str"],
    },
  },
  {
    name: "create_directory",
    description: "Cria uma pasta (e subpastas) no projeto.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Caminho da pasta a criar (relativo ou absoluto)" },
      },
      required: ["path"],
    },
  },
  {
    name: "delete_file",
    description: "Apaga um arquivo ou pasta (pasta: precisa estar vazia, a menos que recursive=true).",
    inputSchema: {
      type: "object",
      properties: {
        path:      { type: "string",  description: "Caminho do arquivo/pasta" },
        recursive: { type: "boolean", description: "Se true, apaga pasta e conteúdo recursivamente" },
      },
      required: ["path"],
    },
  },
  {
    name: "move_file",
    description: "Move ou renomeia um arquivo/pasta.",
    inputSchema: {
      type: "object",
      properties: {
        source:      { type: "string", description: "Caminho de origem" },
        destination: { type: "string", description: "Caminho de destino" },
      },
      required: ["source", "destination"],
    },
  },
  {
    name: "copy_file",
    description: "Copia um arquivo para outro local.",
    inputSchema: {
      type: "object",
      properties: {
        source:      { type: "string", description: "Arquivo de origem" },
        destination: { type: "string", description: "Destino da cópia" },
      },
      required: ["source", "destination"],
    },
  },
  {
    name: "get_file_info",
    description: "Retorna metadados de um arquivo/pasta: tamanho, data, tipo, permissões.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Caminho do arquivo ou pasta" },
      },
      required: ["path"],
    },
  },

  // ── Navegação ──────────────────────────────────────────────────────────
  {
    name: "list_dir",
    description: "Lista arquivos e subpastas dentro de um diretório (não recursivo).",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Caminho da pasta (relativo ao projeto ativo, ou absoluto; padrão: projeto ativo)" },
        show_hidden: { type: "boolean", description: "Mostrar arquivos ocultos (padrão: false)" },
      },
    },
  },
  {
    name: "list_dir_recursive",
    description: "Lista toda a árvore de arquivos do diretório (recursivo, com indentação). Prefira esta a vários list_dir quando precisar ver a estrutura — economiza chamadas.",
    inputSchema: {
      type: "object",
      properties: {
        path:        { type: "string",  description: "Raiz da listagem (padrão: projeto ativo)" },
        max_depth:   { type: "number",  description: "Profundidade máxima (padrão: 4)" },
        show_hidden: { type: "boolean", description: "Mostrar arquivos ocultos (padrão: false)" },
      },
    },
  },
  {
    name: "find_files",
    description: "Busca arquivos por nome/glob no projeto. Suporta padrão glob (ex: *.py, src/**/*.ts). Prefira isto a listar pastas até achar.",
    inputSchema: {
      type: "object",
      properties: {
        pattern:     { type: "string", description: "Padrão de nome de arquivo (glob ou substring)" },
        path:        { type: "string", description: "Pasta raiz da busca (padrão: projeto ativo)" },
        max_results: { type: "number", description: "Máximo de resultados (padrão: 50)" },
      },
      required: ["pattern"],
    },
  },
  {
    name: "search_in_files",
    description:
      "Busca um texto/regex dentro dos arquivos do projeto. Retorna arquivo, linha e trecho para cada match. Prefira buscar aqui a abrir arquivos um por um.",
    inputSchema: {
      type: "object",
      properties: {
        query:       { type: "string",  description: "Texto ou regex a buscar" },
        path:        { type: "string",  description: "Pasta raiz (padrão: projeto ativo)" },
        file_pattern:{ type: "string",  description: "Filtro de extensão, ex: *.js (padrão: todos os textos)" },
        case_sensitive: { type: "boolean", description: "Diferencia maiúsculas (padrão: false)" },
        max_results: { type: "number",  description: "Máximo de resultados (padrão: 30)" },
      },
      required: ["query"],
    },
  },

  // ── Git ────────────────────────────────────────────────────────────────
  {
    name: "git_status",
    description: "Mostra o status do repositório Git (arquivos modificados, staged, untracked).",
    inputSchema: { type: "object", properties: {} },
  },
  {
    name: "git_diff",
    description: "Mostra o diff do repositório ou de um arquivo específico.",
    inputSchema: {
      type: "object",
      properties: {
        path:   { type: "string",  description: "Arquivo específico (opcional; padrão: todos)" },
        staged: { type: "boolean", description: "Mostrar diff staged (--cached)" },
      },
    },
  },
  {
    name: "git_log",
    description: "Mostra o histórico de commits do repositório.",
    inputSchema: {
      type: "object",
      properties: {
        count: { type: "number", description: "Número de commits (padrão: 10)" },
        path:  { type: "string", description: "Arquivo específico (opcional)" },
      },
    },
  },
  {
    name: "git_add",
    description: "Adiciona arquivos ao staging do Git.",
    inputSchema: {
      type: "object",
      properties: {
        path: { type: "string", description: "Arquivo ou pasta a adicionar (padrão: . = tudo)" },
      },
    },
  },
  {
    name: "git_commit",
    description: "Cria um commit com a mensagem fornecida.",
    inputSchema: {
      type: "object",
      properties: {
        message: { type: "string", description: "Mensagem do commit" },
      },
      required: ["message"],
    },
  },
  {
    name: "git_branch",
    description: "Lista as branches do repositório.",
    inputSchema: {
      type: "object",
      properties: {
        all: { type: "boolean", description: "Listar branches remotas também (padrão: false)" },
      },
    },
  },
  {
    name: "git_checkout",
    description: "Troca de branch ou cria uma nova branch.",
    inputSchema: {
      type: "object",
      properties: {
        branch: { type: "string",  description: "Nome da branch" },
        create: { type: "boolean", description: "Se true, cria a branch (-b)" },
      },
      required: ["branch"],
    },
  },

  // ── Terminal ───────────────────────────────────────────────────────────
  {
    name: "run_bash",
    description:
      "Executa um comando de terminal dentro do projeto ativo e retorna a saída formatada como terminal. Use com cuidado — comandos destrutivos não são bloqueados.",
    inputSchema: {
      type: "object",
      properties: {
        command: { type: "string", description: "Comando a executar" },
        timeout: { type: "number", description: "Timeout em ms (padrão: 30000)" },
      },
      required: ["command"],
    },
  },

  // ── Resposta ao terminal ─────────────────────────────────────────────────
  {
    name: "lemove_reply",
    description:
      "Entrega a resposta final ao terminal Lemove Code do usuario. Chame esta ferramenta uma unica vez por resposta quando a mensagem do usuario terminar com [Lemocode], passando em 'text' o texto exato da resposta dada no chat. A ferramenta grava e sinaliza o terminal sozinha — nao use write_file nem run_bash para isso. Responda sempre em texto corrido: nunca use perguntas interativas, botoes ou widgets — se precisar de uma escolha, liste as opcoes numeradas no texto.",
    inputSchema: {
      type: "object",
      properties: {
        text: { type: "string", description: "Texto exato da resposta dada no chat (sem o marcador [Lemocode])" },
      },
      required: ["text"],
    },
    annotations: {
      title: "Entregar resposta ao Lemove Code",
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    },
  },
];

// ── Handlers ──────────────────────────────────────────────────────────────
const server = new Server(
  { name: "lemove-code", version: "0.3.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  // Helper para respostas de erro
  function err(msg) {
    return { content: [{ type: "text", text: msg }], isError: true };
  }

  // Helper para respostas de sucesso
  function ok(text) {
    return { content: [{ type: "text", text: text }] };
  }

  try {
    switch (name) {

      // ── set_project ──────────────────────────────────────────────────
      case "set_project": {
        const target = path.resolve(args.path);
        if (!fs.existsSync(target))
          return err(`Erro: a pasta "${target}" não existe.`);
        if (!fs.statSync(target).isDirectory())
          return err(`Erro: "${target}" não é uma pasta.`);
        activeProject = target;
        return ok(box("Lemove Code", ["Projeto ativo:", activeProject]));
      }

      // ── get_project ──────────────────────────────────────────────────
      case "get_project":
        return ok(box("Projeto ativo", [activeProject]));

      // ── read_file ────────────────────────────────────────────────────
      case "read_file": {
        const filePath = resolveInProject(args.path);
        const raw = fs.readFileSync(filePath, "utf-8");
        let lines = raw.split("\n");
        const start = args.start_line ? Math.max(1, args.start_line) - 1 : 0;
        const end   = args.end_line   ? Math.min(lines.length, args.end_line)   : lines.length;
        lines = lines.slice(start, end);
        const numbered = lines
          .map((line, i) => `${String(i + start + 1).padStart(4, " ")}│ ${line}`)
          .join("\n");
        const rel = path.relative(activeProject, filePath) || filePath;
        return ok(`📄 ${rel}\n\n${numbered}`);
      }

      // ── lemove_reply ─────────────────────────────────────────────────
      case "lemove_reply": {
        const text = String(args.text ?? "");
        if (!text) return err("Erro: 'text' vazio. Passe a resposta completa.");
        const bridgeDir = path.join(os.homedir(), ".lemove-code");
        fs.mkdirSync(bridgeDir, { recursive: true });
        fs.writeFileSync(path.join(bridgeDir, "response.txt"), text, "utf-8");
        fs.writeFileSync(path.join(bridgeDir, "response.done"), "ok", "utf-8");
        return ok("Resposta entregue ao terminal Lemove Code.");
      }

      // ── write_file ───────────────────────────────────────────────────
      case "write_file": {
        const filePath = resolveInProject(args.path);
        fs.mkdirSync(path.dirname(filePath), { recursive: true });
        fs.writeFileSync(filePath, args.content, "utf-8");
        const rel = path.relative(activeProject, filePath) || filePath;
        return ok(`✅ Arquivo salvo: ${rel} (${sizeHuman(Buffer.byteLength(args.content, "utf-8"))})`);
      }

      // ── edit_file ────────────────────────────────────────────────────
      case "edit_file": {
        const filePath = resolveInProject(args.path);
        const original = fs.readFileSync(filePath, "utf-8");
        const count = original.split(args.old_str).length - 1;
        if (count === 0) return err("❌ old_str não foi encontrado no arquivo.");
        if (count > 1)  return err(`❌ old_str aparece ${count} vezes. Inclua mais contexto.`);
        fs.writeFileSync(filePath, original.replace(args.old_str, args.new_str), "utf-8");
        const rel = path.relative(activeProject, filePath) || filePath;
        return ok(`✏️  Edição aplicada em ${rel}`);
      }

      // ── create_directory ─────────────────────────────────────────────
      case "create_directory": {
        const dirPath = resolveInProject(args.path);
        fs.mkdirSync(dirPath, { recursive: true });
        return ok(`📁 Pasta criada: ${path.relative(activeProject, dirPath) || dirPath}`);
      }

      // ── delete_file ──────────────────────────────────────────────────
      case "delete_file": {
        const target = resolveInProject(args.path);
        if (!fs.existsSync(target)) return err(`❌ Não encontrado: ${target}`);
        const stat = fs.statSync(target);
        if (stat.isDirectory()) {
          if (args.recursive) {
            fs.rmSync(target, { recursive: true, force: true });
          } else {
            fs.rmdirSync(target);
          }
        } else {
          fs.unlinkSync(target);
        }
        return ok(`🗑️  Apagado: ${path.relative(activeProject, target) || target}`);
      }

      // ── move_file ────────────────────────────────────────────────────
      case "move_file": {
        const src  = resolveInProject(args.source);
        const dest = resolveInProject(args.destination);
        fs.mkdirSync(path.dirname(dest), { recursive: true });
        fs.renameSync(src, dest);
        return ok(
          `📦 Movido: ${path.relative(activeProject, src)} → ${path.relative(activeProject, dest)}`
        );
      }

      // ── copy_file ────────────────────────────────────────────────────
      case "copy_file": {
        const src  = resolveInProject(args.source);
        const dest = resolveInProject(args.destination);
        fs.mkdirSync(path.dirname(dest), { recursive: true });
        fs.copyFileSync(src, dest);
        return ok(
          `📋 Copiado: ${path.relative(activeProject, src)} → ${path.relative(activeProject, dest)}`
        );
      }

      // ── get_file_info ────────────────────────────────────────────────
      case "get_file_info": {
        const target = resolveInProject(args.path);
        if (!fs.existsSync(target)) return err(`❌ Não encontrado: ${target}`);
        const stat = fs.statSync(target);
        const rel  = path.relative(activeProject, target) || target;
        const info = [
          `Tipo:     ${stat.isDirectory() ? "pasta" : "arquivo"}`,
          `Tamanho:  ${sizeHuman(stat.size)}`,
          `Criado:   ${stat.birthtime.toLocaleString("pt-BR")}`,
          `Modificado: ${stat.mtime.toLocaleString("pt-BR")}`,
        ];
        return ok(box(rel, info));
      }

      // ── list_dir ─────────────────────────────────────────────────────
      case "list_dir": {
        const dirPath = resolveInProject(args.path || ".");
        const showHidden = args.show_hidden || false;
        const entries = fs.readdirSync(dirPath, { withFileTypes: true });
        const lines = entries
          .filter((e) => showHidden || !e.name.startsWith("."))
          .filter((e) => e.name !== "node_modules")
          .sort((a, b) => {
            if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1;
            return a.name.localeCompare(b.name);
          })
          .map((e) => {
            if (e.isDirectory()) return `📁 ${e.name}/`;
            const fp = path.join(dirPath, e.name);
            const sz = ` [${sizeHuman(fs.statSync(fp).size)}]`;
            return `📄 ${e.name}${sz}`;
          });
        const rel = path.relative(activeProject, dirPath) || ".";
        return ok(`${prompt()} ls ${rel}\n\n${lines.join("\n") || "(pasta vazia)"}`);
      }

      // ── list_dir_recursive ───────────────────────────────────────────
      case "list_dir_recursive": {
        const rootDir   = resolveInProject(args.path || ".");
        const maxDepth  = args.max_depth  || 4;
        const showHidden = args.show_hidden || false;
        const IGNORE = new Set(["node_modules", ".git", "__pycache__", ".venv", "dist", "build"]);

        function walkTree(dir, depth, prefix) {
          if (depth > maxDepth) return ["  ".repeat(depth) + "…"];
          const entries = fs.readdirSync(dir, { withFileTypes: true })
            .filter((e) => !IGNORE.has(e.name) && (showHidden || !e.name.startsWith(".")))
            .sort((a, b) => {
              if (a.isDirectory() !== b.isDirectory()) return a.isDirectory() ? -1 : 1;
              return a.name.localeCompare(b.name);
            });
          const lines = [];
          entries.forEach((e, i) => {
            const isLast = i === entries.length - 1;
            const connector = isLast ? "└── " : "├── ";
            const icon = e.isDirectory() ? "📁" : "📄";
            lines.push(`${prefix}${connector}${icon} ${e.name}`);
            if (e.isDirectory()) {
              const childPrefix = prefix + (isLast ? "    " : "│   ");
              lines.push(...walkTree(path.join(dir, e.name), depth + 1, childPrefix));
            }
          });
          return lines;
        }

        const rel = path.relative(activeProject, rootDir) || ".";
        const tree = [`📁 ${rel}/`, ...walkTree(rootDir, 1, "")];
        return ok(tree.join("\n"));
      }

      // ── find_files ───────────────────────────────────────────────────
      case "find_files": {
        const rootDir    = resolveInProject(args.path || ".");
        const pattern    = args.pattern;
        const maxResults = args.max_results || 50;
        const IGNORE = new Set(["node_modules", ".git", "__pycache__", ".venv", "dist", "build"]);
        const results = [];

        function walkFind(dir) {
          if (results.length >= maxResults) return;
          let entries;
          try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
          for (const e of entries) {
            if (IGNORE.has(e.name) || e.name.startsWith(".")) continue;
            const fullPath = path.join(dir, e.name);
            if (e.isDirectory()) {
              walkFind(fullPath);
            } else {
              const rel = path.relative(rootDir, fullPath);
              if (e.name.includes(pattern) || rel.includes(pattern)) {
                results.push(`📄 ${rel}`);
                if (results.length >= maxResults) return;
              }
            }
          }
        }

        walkFind(rootDir);
        if (results.length === 0) return ok(`Nenhum arquivo encontrado para: "${pattern}"`);
        const header = `🔍 ${results.length} arquivo(s) — padrão: "${pattern}"\n`;
        return ok(header + results.join("\n"));
      }

      // ── search_in_files ──────────────────────────────────────────────
      case "search_in_files": {
        const rootDir    = resolveInProject(args.path || ".");
        const query      = args.query;
        const fileExt    = args.file_pattern ? args.file_pattern.replace("*.", "") : null;
        const caseSens   = args.case_sensitive || false;
        const maxResults = args.max_results || 30;
        const IGNORE = new Set(["node_modules", ".git", "__pycache__", ".venv", "dist", "build"]);
        const TEXT_EXT = new Set([
          "js","ts","jsx","tsx","py","lua","json","yaml","yml","toml","md","txt","html","css",
          "scss","sh","bat","ps1","rs","go","java","c","cpp","h","hpp","cs","rb","php","vue","svelte",
        ]);

        const results = [];
        let scanned = 0;

        function walkSearch(dir) {
          if (results.length >= maxResults) return;
          let entries;
          try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return; }
          for (const e of entries) {
            if (IGNORE.has(e.name) || e.name.startsWith(".")) continue;
            const fullPath = path.join(dir, e.name);
            if (e.isDirectory()) {
              walkSearch(fullPath);
            } else {
              const ext = path.extname(e.name).slice(1).toLowerCase();
              if (!TEXT_EXT.has(ext)) continue;
              if (fileExt && ext !== fileExt) continue;
              scanned++;
              try {
                const content = fs.readFileSync(fullPath, "utf-8");
                const lines   = content.split("\n");
                lines.forEach((line, idx) => {
                  if (results.length >= maxResults) return;
                  const haystack = caseSens ? line : line.toLowerCase();
                  const needle   = caseSens ? query : query.toLowerCase();
                  if (haystack.includes(needle)) {
                    const rel = path.relative(rootDir, fullPath);
                    results.push(`${rel}:${idx + 1}:  ${line.trim()}`);
                  }
                });
              } catch { /* arquivo binário ou sem permissão */ }
            }
          }
        }

        walkSearch(rootDir);

        if (results.length === 0)
          return ok(`Nenhum resultado para "${query}" (${scanned} arquivos verificados)`);
        const header = `🔍 ${results.length} resultado(s) para "${query}" (${scanned} arquivos)\n\n`;
        return ok(header + results.join("\n"));
      }

      // ── git_status ───────────────────────────────────────────────────
      case "git_status": {
        const output = execSync("git status", { cwd: activeProject, encoding: "utf-8" });
        return ok(terminalBlock("git status", output.trim()));
      }

      // ── git_diff ─────────────────────────────────────────────────────
      case "git_diff": {
        const staged = args.staged ? "--cached " : "";
        const file   = args.path ? ` -- "${resolveInProject(args.path)}"` : "";
        const cmd    = `git diff ${staged}${file}`.trim();
        const output = execSync(cmd, { cwd: activeProject, encoding: "utf-8", maxBuffer: 5 * 1024 * 1024 });
        return ok(terminalBlock(cmd, output.trim() || "(sem diferenças)"));
      }

      // ── git_log ──────────────────────────────────────────────────────
      case "git_log": {
        const count  = args.count || 10;
        const file   = args.path ? ` -- "${resolveInProject(args.path)}"` : "";
        const cmd    = `git log --oneline -n ${count}${file}`;
        const output = execSync(cmd, { cwd: activeProject, encoding: "utf-8" });
        return ok(terminalBlock(cmd, output.trim()));
      }

      // ── git_add ──────────────────────────────────────────────────────
      case "git_add": {
        const target = args.path ? resolveInProject(args.path) : ".";
        const output = execSync(`git add "${target}"`, { cwd: activeProject, encoding: "utf-8" });
        return ok(`✅ git add concluído: ${args.path || "."}`);
      }

      // ── git_commit ───────────────────────────────────────────────────
      case "git_commit": {
        const output = execSync(
          `git commit -m "${args.message.replace(/"/g, '\\"')}"`,
          { cwd: activeProject, encoding: "utf-8" }
        );
        return ok(terminalBlock("git commit", output.trim()));
      }

      // ── git_branch ───────────────────────────────────────────────────
      case "git_branch": {
        const flag   = args.all ? "-a" : "";
        const output = execSync(`git branch ${flag}`, { cwd: activeProject, encoding: "utf-8" });
        return ok(terminalBlock(`git branch ${flag}`, output.trim()));
      }

      // ── git_checkout ─────────────────────────────────────────────────
      case "git_checkout": {
        const flag   = args.create ? "-b " : "";
        const output = execSync(`git checkout ${flag}"${args.branch}"`, {
          cwd: activeProject, encoding: "utf-8",
        });
        return ok(terminalBlock(`git checkout ${flag}${args.branch}`, output.trim()));
      }

      // ── run_bash ─────────────────────────────────────────────────────
      case "run_bash": {
        const timeout = args.timeout || 30000;
        let output;
        try {
          output = execSync(args.command, {
            cwd:       activeProject,
            encoding:  "utf-8",
            timeout,
            maxBuffer: 5 * 1024 * 1024,
          });
        } catch (execErr) {
          output = (execErr.stdout || "") + (execErr.stderr || execErr.message);
          return { content: [{ type: "text", text: terminalBlock(args.command, output || "(sem saída)") }], isError: true };
        }
        return ok(terminalBlock(args.command, output || "(sem saída)"));
      }

      default:
        return err(`Ferramenta desconhecida: ${name}`);
    }
  } catch (err2) {
    return err(`❌ Erro: ${err2.message}`);
  }
});

// ── Main ──────────────────────────────────────────────────────────────────
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error(`Lemove Code MCP v0.3.0 rodando. Projeto ativo: ${shortPath(activeProject)}`);
}

main().catch((err) => {
  console.error("Erro fatal no Lemove Code MCP:", err);
  process.exit(1);
});
