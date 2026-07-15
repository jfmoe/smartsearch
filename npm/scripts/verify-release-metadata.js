const fs = require("node:fs");
const path = require("node:path");

const expectedVersion = process.argv[2];
const packageRoot = path.resolve(__dirname, "..", "..");
const packageJson = JSON.parse(
  fs.readFileSync(path.join(packageRoot, "package.json"), "utf8")
);
const packageLock = JSON.parse(
  fs.readFileSync(path.join(packageRoot, "package-lock.json"), "utf8")
);
const pyproject = fs.readFileSync(path.join(packageRoot, "pyproject.toml"), "utf8");
const pyprojectVersion = /^version = "([^"]+)"$/m.exec(pyproject)?.[1];

const versions = {
  "package.json": packageJson.version,
  "package-lock.json": packageLock.version,
  "package-lock.json packages root": packageLock.packages?.[""]?.version,
  "pyproject.toml": pyprojectVersion
};
const names = {
  "package.json": packageJson.name,
  "package-lock.json": packageLock.name,
  "package-lock.json packages root": packageLock.packages?.[""]?.name
};

function fail(message) {
  console.error(`release metadata check failed: ${message}`);
  process.exit(1);
}

if (new Set(Object.values(versions)).size !== 1) {
  fail(`version drift: ${JSON.stringify(versions)}`);
}
if (expectedVersion && packageJson.version !== expectedVersion) {
  fail(`expected version ${expectedVersion}, found ${packageJson.version}`);
}
if (new Set(Object.values(names)).size !== 1 || packageJson.name !== "@jfmoe/smart-search") {
  fail(`package identity drift: ${JSON.stringify(names)}`);
}

console.log(`release metadata is consistent for ${packageJson.name}@${packageJson.version}`);
