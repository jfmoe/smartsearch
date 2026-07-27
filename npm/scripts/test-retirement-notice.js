const assert = require("node:assert/strict");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const packageRoot = path.resolve(__dirname, "..", "..");
const result = spawnSync(process.execPath, ["npm/scripts/postinstall.js"], {
  cwd: packageRoot,
  encoding: "utf8",
  windowsHide: true
});

assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /https:\/\/github\.com\/jfmoe\/forager/);
assert.match(result.stdout, /npx skills add jfmoe\/forager/);
