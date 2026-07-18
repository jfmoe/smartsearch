const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const packageRoot = path.resolve(__dirname, "..", "..");
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const output = execFileSync(npmCommand, ["pack", "--dry-run", "--json"], {
  cwd: packageRoot,
  encoding: "utf8"
});
const packedFiles = new Set(JSON.parse(output)[0].files.map((entry) => entry.path));

function treeFiles(relativeRoot) {
  const absoluteRoot = path.join(packageRoot, relativeRoot);
  const pending = [absoluteRoot];
  const files = [];
  while (pending.length) {
    const directory = pending.pop();
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const absolutePath = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        pending.push(absolutePath);
      } else if (entry.isFile()) {
        files.push(path.relative(packageRoot, absolutePath).split(path.sep).join("/"));
      }
    }
  }
  return files.sort();
}

const publicSkillFiles = treeFiles("skills/smart-search-cli");
const packagedSkillFiles = treeFiles("src/smart_search/assets/skills/smart-search-cli");
const packagedRuntimeFiles = treeFiles("src/smart_search").filter((file) => file.endsWith(".py"));
const requiredFiles = [
  "package.json",
  "pyproject.toml",
  "README.md",
  "README.zh-CN.md",
  "LICENSE",
  "npm/bin/smart-search.js",
  "npm/scripts/postinstall.js",
  "npm/scripts/verify-release-metadata.js",
  "npm/scripts/verify-release-policy.js",
  "npm/scripts/verify-pack.js",
  ...publicSkillFiles,
  ...packagedSkillFiles,
  ...packagedRuntimeFiles
];
const missing = requiredFiles.filter((file) => !packedFiles.has(file));
const forbidden = [...packedFiles].filter(
  (file) =>
    file.startsWith(".smart-search-python/") ||
    file.startsWith(".smart-search/") ||
    file.startsWith(".venv/") ||
    file.startsWith(".pytest_cache/") ||
    file.startsWith("tests/") ||
    file.includes("/__pycache__/") ||
    file.endsWith(".pyc") ||
    file.endsWith(".tmp") ||
    file.endsWith(".temp") ||
    file.endsWith(".tgz") ||
    file.endsWith(".log") ||
    file.endsWith("/.DS_Store") ||
    path.posix.basename(file).startsWith(".tmp") ||
    file === "config.json" ||
    file.endsWith("/config.json") ||
    file === ".env" ||
    file.endsWith("/.env") ||
    file === ".coverage" ||
    file === "skills-lock.json" ||
    file === "uv.lock"
);

if (missing.length || forbidden.length) {
  console.error(`npm pack content check failed: missing=${missing.join(",")} forbidden=${forbidden.join(",")}`);
  process.exit(1);
}

console.log(
  `npm pack content check passed (${packedFiles.size} files; ` +
    `${publicSkillFiles.length} public Skill files; ` +
    `${packagedSkillFiles.length} packaged Skill files; ` +
    `${packagedRuntimeFiles.length} runtime files)`
);
