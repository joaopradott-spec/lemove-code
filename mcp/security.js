"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");

const AUTH_FILE = path.join(os.homedir(), ".lemove-code", "authorized-projects.json");

function canonicalExisting(target) {
  return fs.realpathSync.native ? fs.realpathSync.native(target) : fs.realpathSync(target);
}

function nearestExisting(target) {
  let cursor = target;
  while (!fs.existsSync(cursor)) {
    const parent = path.dirname(cursor);
    if (parent === cursor) break;
    cursor = parent;
  }
  return cursor;
}

function isWithin(root, target) {
  const rel = path.relative(root, target);
  return rel === "" || (!rel.startsWith(`..${path.sep}`) && rel !== ".." && !path.isAbsolute(rel));
}

function readAuthorizedProjects() {
  try {
    const payload = JSON.parse(fs.readFileSync(AUTH_FILE, "utf8"));
    const entries = Array.isArray(payload) ? payload : payload.projects;
    return (entries || [])
      .map((item) => typeof item === "string" ? item : item.path)
      .filter(Boolean)
      .filter(fs.existsSync)
      .map(canonicalExisting);
  } catch {
    return [];
  }
}

class ProjectGuard {
  constructor(initialProject) {
    const candidate = path.resolve(initialProject || process.cwd());
    if (!fs.existsSync(candidate) || !fs.statSync(candidate).isDirectory()) {
      throw new Error(`Pasta inicial invalida: ${candidate}`);
    }
    this.root = canonicalExisting(candidate);
    this.fixedRoot = Boolean(initialProject);
  }

  setProject(requested) {
    const target = canonicalExisting(path.resolve(requested));
    if (!fs.statSync(target).isDirectory()) throw new Error("O projeto precisa ser uma pasta.");
    const allowed = this.fixedRoot
      ? [this.root]
      : [...readAuthorizedProjects(), this.root];
    if (!allowed.some((root) => isWithin(root, target))) {
      throw new Error(`Projeto nao autorizado: ${target}. Abra essa pasta primeiro no Lemove Code.`);
    }
    this.root = target;
    return target;
  }

  resolve(userPath = ".", { allowRoot = true } = {}) {
    const lexical = path.resolve(this.root, String(userPath));
    if (!isWithin(this.root, lexical)) throw new Error("Caminho fora do projeto ativo.");
    const ancestor = canonicalExisting(nearestExisting(lexical));
    if (!isWithin(this.root, ancestor)) throw new Error("Link simbolico aponta para fora do projeto.");
    if (fs.existsSync(lexical)) {
      const real = canonicalExisting(lexical);
      if (!isWithin(this.root, real)) throw new Error("Caminho real fora do projeto ativo.");
    }
    if (!allowRoot && lexical === this.root) throw new Error("A raiz do projeto e protegida.");
    return lexical;
  }
}

module.exports = { ProjectGuard, isWithin, readAuthorizedProjects };
