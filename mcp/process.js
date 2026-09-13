"use strict";

const { spawnSync } = require("child_process");

function runProgram(program, args, options = {}) {
  const result = spawnSync(program, args, {
    cwd: options.cwd,
    encoding: "utf8",
    timeout: options.timeout || 30000,
    maxBuffer: options.maxBuffer || 5 * 1024 * 1024,
    shell: false,
    windowsHide: true,
  });
  const output = `${result.stdout || ""}${result.stderr || ""}`.trim();
  if (result.error) throw result.error;
  if (result.status !== 0) {
    const error = new Error(output || `${program} terminou com codigo ${result.status}`);
    error.output = output;
    throw error;
  }
  return output;
}

module.exports = { runProgram };
