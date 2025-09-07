const fs = require("fs");
const { spawn } = require("child_process");

const payloadPath = "./fixtures/convert_sample.json";  // relative to this folder
const payload = fs.readFileSync(payloadPath, "utf8");

const p = spawn("node", ["./sparka_bridge.mjs"], {
  cwd: __dirname,
  stdio: ["pipe", "inherit", "inherit"],
});
p.stdin.write(payload);
p.stdin.end();
p.on("exit", (code) => process.exit(code ?? 0));
