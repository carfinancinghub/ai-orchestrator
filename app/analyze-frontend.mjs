import { globby } from "globby";
import fs from "node:fs/promises";
import path from "node:path";
import * as babel from "@babel/parser";
import traverse from "@babel/traverse";
import * as t from "@babel/types";

const FRONTEND = process.env.FRONTEND_PATH || "C:/Backup_Projects/CFH/frontend";
const stamp = (process.env.stamp && process.env.stamp.trim())
  ? process.env.stamp.trim()
  : new Date().toISOString().replace(/[-:TZ]/g,"").slice(0,15);

const outDir = path.join(process.cwd(), "reports", "analysis", stamp);
await fs.mkdir(outDir, { recursive: true });

// IMPORTANT: use cwd = FRONTEND and relative patterns. Ask for absolute paths back.
const files = await globby(
  ["src/**/*.{ts,tsx,js,jsx}"],
  {
    cwd: FRONTEND.replace(/\\/g,"/"),
    absolute: true,
    gitignore: true,
    ignore: [
      "**/node_modules/**",
      "**/dist/**",
      "**/.{git,idea,cache,output,temp}/**",
      "**/conversion/**",
      "**/backend/**"
    ]
  }
);

const results = [];
for (const f of files) {
  const code = await fs.readFile(f, "utf8").catch(() => "");
  if (!code) { results.push({ file: f, parseError: "empty or unreadable" }); continue; }

  let ast;
  try {
    ast = babel.parse(code, {
      sourceType: "module",
      plugins: [
        "jsx",
        "typescript",
        ["decorators", { version: "legacy" }],
        "classProperties",
        "classPrivateProperties",
        "classPrivateMethods",
        "topLevelAwait",
      ],
    });
  } catch (e) {
    results.push({ file: f, parseError: String(e.message || e) });
    continue;
  }

  const info = {
    file: f,
    exports: [],
    hasDefaultExport: false,
    reactComponent: false,
    hooks: [],
    apis: [],
    sideEffects: [],
    imports: [],
  };

  traverse.default(ast, {
    ImportDeclaration(p) {
      const src = p.node.source.value;
      info.imports.push(src);
      if (/axios|swr|ky|@tanstack\/query/.test(src)) info.apis.push(`import:${src}`);
    },
    CallExpression(p) {
      const c = p.node.callee;
      const name = t.isIdentifier(c) ? c.name :
                   (t.isMemberExpression(c) && t.isIdentifier(c.property)) ? c.property.name : "";
      if (name === "fetch") info.apis.push("fetch()");
      if (["log","warn","error"].includes(name)) info.sideEffects.push(`console.${name}`);
      if (t.isMemberExpression(c) && t.isIdentifier(c.object, { name: "localStorage" }))
        info.sideEffects.push("localStorage");
    },
    ExportDefaultDeclaration() { info.hasDefaultExport = true; },
    ExportNamedDeclaration(p) {
      const d = p.node.declaration;
      if (d) {
        if (t.isFunctionDeclaration(d) && d.id) info.exports.push(d.id.name);
        if (t.isVariableDeclaration(d)) {
          d.declarations.forEach(v => { if (t.isIdentifier(v.id)) info.exports.push(v.id.name); });
        }
      }
      (p.node.specifiers || []).forEach(s => {
        if (t.isIdentifier(s.exported)) info.exports.push(s.exported.name);
      });
    },
    FunctionDeclaration(p) {
      if (!p.node.id) return;
      const name = p.node.id.name;
      if (/^[A-Z]/.test(name)) {
        let returnsJSX = false;
        p.traverse({
          JSXElement() { returnsJSX = true; },
          CallExpression(inner) {
            const ci = inner.node.callee;
            if (t.isMemberExpression(ci) &&
                t.isIdentifier(ci.object, { name: "React" }) &&
                t.isIdentifier(ci.property, { name: "createElement" })) {
              returnsJSX = true;
            }
          }
        });
        if (returnsJSX) info.reactComponent = true;
      }
    },
    VariableDeclarator(p) {
      if (t.isIdentifier(p.node.id) && /^[A-Z]/.test(p.node.id.name)) {
        let returnsJSX = false;
        const init = p.node.init;
        if (t.isArrowFunctionExpression(init) || t.isFunctionExpression(init)) {
          traverse.default(init.body, { JSXElement() { returnsJSX = true; } }, p.scope, p.state, p);
        }
        if (returnsJSX) info.reactComponent = true;
      }
    },
    Identifier(p) {
      if (/^use[A-Z]/.test(p.node.name)) info.hooks.push(p.node.name);
    },
  });

  info.hooks = [...new Set(info.hooks)].sort();
  info.apis = [...new Set(info.apis)].sort();
  info.sideEffects = [...new Set(info.sideEffects)].sort();
  info.imports = [...new Set(info.imports)].sort();
  info.exports = [...new Set(info.exports)].sort();

  results.push(info);
}

await fs.writeFile(path.join(outDir, "plan.json"), JSON.stringify(results, null, 2), "utf8");

const lines = [];
lines.push(`# Frontend Analysis (${stamp})\n`);
lines.push(`Scanned files: ${results.length}\n`);
for (const r of results) {
  const rel = path.relative(FRONTEND, r.file).replace(/\\/g,"/");
  lines.push(`## ${rel}`);
  if (r.parseError) { lines.push(`- ❌ Parse error: \`${r.parseError}\`\n`); continue; }
  lines.push(`- Exports: ${r.exports.length ? '\`' + r.exports.join('\`, \`') + '\`' : '_none_'}${r.hasDefaultExport ? ' (default export)' : ''}`);
  lines.push(`- React component: ${r.reactComponent ? 'yes' : 'no'}`);
  if (r.hooks.length) lines.push(`- Hooks: \`${r.hooks.join('`, `')}\``);
  if (r.apis.length)  lines.push(`- API: \`${r.apis.join('`, `')}\``);
  if (r.sideEffects.length) lines.push(`- Side-effects: \`${r.sideEffects.join('`, `')}\``);
  if (r.imports.length) lines.push(`- Imports: \`${r.imports.slice(0,10).join('`, `')}${r.imports.length>10?'` …':''}\``);
  const sugg = [];
  if (r.reactComponent && !rel.endsWith('.tsx')) sugg.push('🔁 consider `.tsx`');
  if (r.exports.length === 0) sugg.push('🧹 dead code check');
  if (sugg.length) lines.push(`- Suggestions: ${sugg.join('; ')}`);
  lines.push('');
}
await fs.writeFile(path.join(outDir, "report.md"), lines.join("\n"), "utf8");

console.log(`Wrote: ${path.join(outDir, "report.md")}`);
