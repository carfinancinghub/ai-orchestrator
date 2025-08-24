// tools/make-review-pack.mjs
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";

const stripBom = s => (typeof s === "string" ? s.replace(/^\uFEFF/, "") : s);

async function main() {
  const [,, inputJsonPath, outPath] = process.argv;
  if (!inputJsonPath || !outPath) {
    console.error("Usage: node tools/make-review-pack.mjs <review_input.json> <out.txt|.md>");
    process.exit(1);
  }

  const raw = stripBom(await readFile(resolve(inputJsonPath), "utf8"));
  const parsed = JSON.parse(raw);

  const project = parsed.project ?? "PROJECT";
  const prompt  = stripBom(parsed.prompt ?? "");
  let codemapPretty = "";
  try {
    const cm = JSON.parse(stripBom(parsed.codemap ?? "{}"));
    codemapPretty = JSON.stringify(cm, null, 2);
  } catch {
    codemapPretty = stripBom(parsed.codemap ?? "{}");
  }

  const ts = new Date().toISOString();
  const body = [
    `# AI Codebase Review: ${project}`,
    ``,
    `Generated: ${ts}`,
    ``,
    `## Prompt`,
    ``,
    prompt,
    ``,
    `## Codemap (JSON)`,
    ``,
    "```json",
    codemapPretty,
    "```",
    ""
  ].join("\n");

  await writeFile(resolve(outPath), body, "utf8");
  console.log("WROTE", resolve(outPath));
}

main().catch(e => { console.error(e); process.exit(1); });
