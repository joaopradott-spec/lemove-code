// Cliente de teste simples: conversa com o server.js via stdio,
// simulando o que o Claude Desktop faria, pra validar as ferramentas
// antes de plugar no app de verdade.
const { Client } = require("@modelcontextprotocol/sdk/client/index.js");
const { StdioClientTransport } = require("@modelcontextprotocol/sdk/client/stdio.js");

async function main() {
  const transport = new StdioClientTransport({
    command: "node",
    args: ["server.js", "/tmp/projeto-teste-a"],
  });

  const client = new Client({ name: "lemove-test-client", version: "0.1.0" }, { capabilities: {} });
  await client.connect(transport);

  console.log("--- Ferramentas disponíveis ---");
  const tools = await client.listTools();
  console.log(tools.tools.map((t) => t.name).join(", "));

  console.log("\n--- list_dir ---");
  console.log((await client.callTool({ name: "list_dir", arguments: {} })).content[0].text);

  console.log("\n--- read_file exemplo.js ---");
  console.log((await client.callTool({ name: "read_file", arguments: { path: "exemplo.js" } })).content[0].text);

  console.log("\n--- write_file novo.txt ---");
  console.log(
    (await client.callTool({ name: "write_file", arguments: { path: "novo.txt", content: "criado pelo Lemove Code!" } })).content[0].text
  );

  console.log("\n--- edit_file exemplo.js ---");
  console.log(
    (
      await client.callTool({
        name: "edit_file",
        arguments: { path: "exemplo.js", old_str: "hello lemove", new_str: "olá do Lemove Code" },
      })
    ).content[0].text
  );

  console.log("\n--- read_file exemplo.js (depois da edição) ---");
  console.log((await client.callTool({ name: "read_file", arguments: { path: "exemplo.js" } })).content[0].text);

  console.log("\n--- run_bash (ls -la) ---");
  console.log((await client.callTool({ name: "run_bash", arguments: { command: "ls -la" } })).content[0].text);

  console.log("\n--- teste de segurança: tentar sair da pasta base ---");
  try {
    const result = await client.callTool({ name: "read_file", arguments: { path: "../server.js" } });
    console.log("Resultado (deveria ser erro):", JSON.stringify(result));
  } catch (e) {
    console.log("Bloqueado como esperado (exceção):", e.message);
  }

  await client.close();
}

main().catch((e) => {
  console.error("Erro no teste:", e);
  process.exit(1);
});
