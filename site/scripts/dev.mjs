import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
const python =
  process.env.TRENDSCULPT_PYTHON ||
  (existsSync(".venv/bin/python") ? ".venv/bin/python" : "python");
const children = [
  spawn(
    python,
    [
      "-m",
      "uvicorn",
      "server.app:app",
      "--reload",
      "--reload-dir",
      "server",
      "--host",
      "127.0.0.1",
      "--port",
      "8000",
    ],
    { stdio: "inherit", env: { ...process.env, OPENBLAS_NUM_THREADS: "2" } },
  ),
  spawn(
    "node",
    [
      "node_modules/vite/bin/vite.js",
      "--host",
      "0.0.0.0",
      "--port",
      "5174",
      "--strictPort",
    ],
    { stdio: "inherit" },
  ),
];
let stopping = false;
function stop() {
  if (stopping) return;
  stopping = true;
  for (const c of children) c.kill("SIGTERM");
}
process.on("SIGINT", stop);
process.on("SIGTERM", stop);
for (const c of children) {
  c.on("error", (e) => {
    console.error(e.message);
    stop();
    process.exitCode = 1;
  });
  c.on("exit", (code) => {
    if (!stopping) {
      stop();
      process.exitCode = code || 0;
    }
  });
}
