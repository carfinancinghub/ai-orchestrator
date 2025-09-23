// Path: app/services/llm/test_bridge.cjs
const fs = require("fs");
const { spawn } = require("child_process");

const payloadPath = "app/services/llm/fixtures/convert_sample.json";
const payload = fs.readFileSync(payloadPath, "utf8");

const p = spawn("node", ["app/services/llm/sparka_bridge.mjs"], {
  stdio: ["pipe", "inherit", "inherit"],
});
p.stdin.write(payload);
p.stdin.end();
p.on("exit", (code) => process.exit(code ?? 0));
