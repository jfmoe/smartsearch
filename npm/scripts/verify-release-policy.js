const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..", "..");
const legacyOwner = "konba" + "kuyomu";
const legacyScope = `@${legacyOwner}/smart-search`;
const legacyRepository = `${legacyOwner}/smartsearch`;
const skippedDirectories = new Set([
  ".git",
  ".pytest_cache",
  ".smart-search-python",
  ".trellis",
  "build",
  "node_modules"
]);

function isAllowedLegacyContext(relativePath) {
  return (
    relativePath.startsWith(".github/releases/") ||
    relativePath === "docs/release/upstream-baseline.md" ||
    relativePath.startsWith("docs/research/")
  );
}

function visit(directory, violations) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    if (entry.isDirectory()) {
      if (!skippedDirectories.has(entry.name) && !entry.name.endsWith(".egg-info")) {
        visit(path.join(directory, entry.name), violations);
      }
      continue;
    }
    if (!entry.isFile()) {
      continue;
    }
    if (entry.name.endsWith(".egg-info")) {
      continue;
    }
    const filePath = path.join(directory, entry.name);
    const relativePath = path.relative(root, filePath).split(path.sep).join("/");
    const text = fs.readFileSync(filePath, "utf8");
    if (
      !isAllowedLegacyContext(relativePath) &&
      (text.includes(legacyOwner) || text.includes(legacyScope) || text.includes(legacyRepository))
    ) {
      violations.push(relativePath);
    }
  }
}

const violations = [];
visit(root, violations);
if (violations.length > 0) {
  console.error("legacy release identity is only permitted in historical, research, or upstream-baseline records:");
  for (const violation of violations) {
    console.error(`- ${violation}`);
  }
  process.exit(1);
}

console.log("release identity allowlist check passed");
