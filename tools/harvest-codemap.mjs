import { globby } from "globby";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { resolve, relative } from "node:path";
import { existsSync } from "node:fs";

function usage() {
  console.log("Usage: node tools/harvest-codemap.mjs --root <abs-path> [--project <name>] [--frontend-only]");
  process.exit(1);
}

const args = Object.fromEntries(
  process.argv.slice(2).reduce((acc, cur, i, arr) => {
    if (cur.startsWith("--")) acc.push([cur.replace(/^--/,""), arr[i+1]?.startsWith("--")? true : arr[i+1]]);
    return acc;
  }, [])
);

const root = args.root;
if (!root) usage();
const project = args.project || (root.split(/[\\\/]/).slice(-1)[0]);
const frontendOnly = !!args["frontend-only"];

async function safeReadJSON(p) {
  try { return JSON.parse(await readFile(p, "utf8")); } catch { return null; }
}

function extractAliasesFromVite(text){
  // Find the alias: { ... } block and grab "key": ".../path"
  const out = {};
  const m = /alias\s*:\s*{([\s\S]*?)}/m.exec(text);
  if(!m) return out;
  const block = m[1];
  // Very forgiving: captures key and any quoted ./relative or src/... path on the right
  const re = /["']([^"']+)["']\s*:\s*[^,\n]*?["']\.?\/([^"']+)["']/g;
  let mm;
  while((mm = re.exec(block))){
    const key = mm[1];
    const rel = mm[2];
    if (key && rel) out[key] = rel;
  }
  return out;
}

async function harvestOne(baseDir, label) {
  const srcDir = resolve(baseDir, "src");
  if (!existsSync(srcDir)) return null;

  const files = await globby(["**/*.{js,jsx,ts,tsx,json,css}"], {
    cwd: srcDir,
    gitignore: true,
    dot: false,
    ignore: [
      "**/node_modules/**","**/.git/**","**/dist/**","**/build/**",
      "**/.next/**","**/.vite/**","**/coverage/**","**/out/**","**/.turbo/**"
    ],
  });

  const entries = [];
  for (const f of files) {
    const full = resolve(srcDir, f);
    let code = "";
    try { code = await readFile(full, "utf8"); } catch {}
    const imports = [];
    const re = /(?:from|import)\s*['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)|import\(\s*['"]([^'"]+)['"]\s*\)/g;
    let m; while ((m = re.exec(code))) {
      const v = m[1] ?? m[2] ?? m[3]; if (v) imports.push(v);
    }
    entries.push({ path: f, imports });
  }

  const aliases = {};
  for (const cfg of ["vite.config.ts","vite.config.js"]) {
    const p = resolve(baseDir, cfg);
    if (!existsSync(p)) continue;
    const text = await readFile(p, "utf8").catch(()=> "");
    Object.assign(aliases, extractAliasesFromVite(text));
  }

  const ts = await safeReadJSON(resolve(baseDir, "tsconfig.json"));
  if (ts?.compilerOptions?.paths) aliases.tsconfigPaths = ts.compilerOptions.paths;

  const pkg = await safeReadJSON(resolve(baseDir, "package.json"));

  return {
    label,
    dir: relative(root, baseDir) || ".",
    aliases,
    dependencies: pkg?.dependencies ?? {},
    devDependencies: pkg?.devDependencies ?? {},
    files: entries
  };
}

const outDir = resolve(process.cwd(), "reports", project);
await mkdir(outDir, { recursive: true });

const results = [];
if (!frontendOnly) {
  for (const name of ["frontend","web","app"]) results.push(await harvestOne(resolve(root, name), name));
  for (const name of ["backend","api","server"]) results.push(await harvestOne(resolve(root, name), name));
}
results.push(await harvestOne(root, "root"));

const payload = {
  generatedAt: new Date().toISOString(),
  root,
  segments: results.filter(Boolean)
};

await writeFile(resolve(outDir, "codemap.json"), JSON.stringify(payload, null, 2), "utf8");
console.log("WROTE", resolve(outDir, "codemap.json"));
