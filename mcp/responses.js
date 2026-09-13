"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const MAX_RESPONSE_BYTES = 5 * 1024 * 1024;

function safeId(value, fallback) {
  const id = String(value || fallback || "spontaneous");
  if (!/^[a-zA-Z0-9_-]{1,128}$/.test(id)) throw new Error("Identificador de resposta invalido.");
  return id;
}

function atomicWrite(filePath, content) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const temp = `${filePath}.${process.pid}.${Date.now()}.tmp`;
  fs.writeFileSync(temp, content, { encoding: "utf8", mode: 0o600 });
  fs.renameSync(temp, filePath);
}

function deliverResponse({ text, request_id, session_id }) {
  const content = String(text ?? "");
  if (!content) throw new Error("'text' nao pode ser vazio.");
  if (Buffer.byteLength(content, "utf8") > MAX_RESPONSE_BYTES) {
    throw new Error("Resposta excede o limite de 5 MB.");
  }
  const requestId = safeId(request_id, `spontaneous-${Date.now()}`);
  const sessionId = safeId(session_id, "default");
  const outbox = path.join(os.homedir(), ".lemove-code", "outbox");
  const envelope = {
    protocolVersion: 1,
    requestId,
    sessionId,
    createdAt: new Date().toISOString(),
    status: "completed",
    content,
  };
  atomicWrite(path.join(outbox, `${requestId}.json`), JSON.stringify(envelope));
  return envelope;
}

module.exports = { atomicWrite, deliverResponse, safeId };
