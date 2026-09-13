"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");
const { ProjectGuard, isWithin } = require("../mcp/security");
const { runProgram } = require("../mcp/process");

test("ProjectGuard mantem caminhos dentro da raiz", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "lemove-guard-"));
  fs.mkdirSync(path.join(root, "src"));
  const guard = new ProjectGuard(root);
  assert.equal(guard.resolve("src").toLowerCase(), path.join(guard.root, "src").toLowerCase());
  assert.throws(() => guard.resolve("../fora.txt"), /fora do projeto/);
  assert.throws(() => guard.resolve(".", { allowRoot: false }), /raiz do projeto/);
});

test("isWithin nao aceita prefixos parecidos", () => {
  const root = path.resolve("project");
  assert.equal(isWithin(root, path.join(root, "file.txt")), true);
  assert.equal(isWithin(root, path.resolve("project-evil", "file.txt")), false);
});

test("runProgram passa argumentos sem interpretacao do shell", () => {
  const value = 'texto;echo NAO_EXECUTAR & mais';
  const output = runProgram(process.execPath, ["-e", "process.stdout.write(process.argv[1])", value]);
  assert.equal(output, value);
});
