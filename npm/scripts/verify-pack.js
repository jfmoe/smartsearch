const { execFileSync } = require("node:child_process");
const path = require("node:path");

const packageRoot = path.resolve(__dirname, "..", "..");
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const output = execFileSync(npmCommand, ["pack", "--dry-run", "--json"], {
  cwd: packageRoot,
  encoding: "utf8"
});
const packedFiles = new Set(JSON.parse(output)[0].files.map((entry) => entry.path));
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
  "skills/smart-search-cli/SKILL.md",
  "src/smart_search/assets/skills/smart-search-cli/SKILL.md"
];
const missing = requiredFiles.filter((file) => !packedFiles.has(file));
const forbidden = [...packedFiles].filter(
  (file) => file.startsWith(".smart-search-python/") || file.startsWith("tests/")
);

if (missing.length || forbidden.length) {
  console.error(`npm pack content check failed: missing=${missing.join(",")} forbidden=${forbidden.join(",")}`);
  process.exit(1);
}

console.log(`npm pack content check passed (${packedFiles.size} files)`);
