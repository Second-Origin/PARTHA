import { spawnSync } from "node:child_process";
import http from "node:http";

function run(command, args) {
  const result = spawnSync(command, args, { stdio: "inherit", shell: false });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(`${command} ${args.join(" ")} failed with exit code ${result.status}`);
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function checkReady() {
  return new Promise((resolve) => {
    const request = http.get("http://127.0.0.1:8000/ready", { timeout: 5000 }, (response) => {
      response.resume();
      resolve(response.statusCode === 200);
    });
    request.on("timeout", () => {
      request.destroy();
      resolve(false);
    });
    request.on("error", () => resolve(false));
  });
}

async function main() {
  run("docker", ["compose", "config"]);
  try {
    run("docker", ["compose", "up", "--build", "-d"]);
    for (let attempt = 0; attempt < 30; attempt += 1) {
      if (await checkReady()) return;
      await sleep(2000);
    }
    run("docker", ["compose", "logs", "api", "postgres", "redis"]);
    throw new Error("Compose API did not become ready.");
  } finally {
    run("docker", ["compose", "down", "-v"]);
  }
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
