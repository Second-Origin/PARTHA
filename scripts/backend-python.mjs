import { existsSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const repoRoot = process.cwd();
const backendDir = join(repoRoot, "apps", "backend");
const candidates = [
  join(backendDir, ".venv", "Scripts", "python.exe"),
  join(backendDir, ".venv", "bin", "python"),
  "python",
];

const python = candidates.find((candidate) => candidate === "python" || existsSync(candidate));
const result = spawnSync(python, process.argv.slice(2), {
  cwd: backendDir,
  stdio: "inherit",
  shell: false,
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

process.exit(result.status ?? 1);
