import fs from "node:fs/promises";
import path from "node:path";

const FRONTEND = process.env.FRONTEND_PATH || "C:/Backup_Projects/CFH/frontend";
const PLAN = process.env.PLAN_PATH || path.join(process.cwd(), "reports","analysis", (process.env.stamp??""), "plan.json");
const DRY = process.env.DRY_RUN === "0" ? false : true;

const plan = JSON.parse(await fs.readFile(PLAN,"utf8"));
const writes = [];

for (const r of plan) {
  if (r.parseError) continue;
  if (r.reactComponent && !r.file.endsWith(".tsx")) {
    const tsx = r.file.replace(/\.(jsx|js|ts)$/i, ".tsx");
    const rel = path.relative(FRONTEND, tsx).replace(/\\/g,"/");
    const stub = `/* AUTO-GENERATED STUB: review before use */
import React from 'react';
export default function ComponentStub(): JSX.Element {
  return <div data-auto-stub="${rel}">TODO: port ${rel}</div>;
}
`;
    writes.push({ to: tsx, content: stub });
  }
}

for (const w of writes) {
  if (DRY) {
    console.log(`[dry] would write ${w.to}`);
  } else {
    await fs.mkdir(path.dirname(w.to), { recursive:true });
    try { await fs.access(w.to); console.log(`skip (exists): ${w.to}`); }
    catch { await fs.writeFile(w.to, w.content, "utf8"); console.log(`wrote: ${w.to}`); }
  }
}
console.log(`stubs planned: ${writes.length}  dry=${DRY}`);

