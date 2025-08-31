// Path: app/services/llm/sparka_bridge.mjs
/**
 * Node bridge using the "ai" package with fallback to OpenAI REST.
 * stdin:  { op, file_path, code, extra, env }
 * stdout: plain string; empty on failure.
 *
 * Install deps:
 *   npm i ai openai
 */
import { generateText } from "ai";

const readStdin = async () => {
  const chunks = [];
  for await (const chunk of process.stdin) chunks.push(chunk);
  return Buffer.concat(chunks).toString("utf8");
};

const prompts = {
  convert: (code, file) => `Convert the following JS/JSX to idiomatic TypeScript/TSX. Keep behavior identical, avoid 'any', preserve comments/TODO.
File: ${file}
\`\`\`javascript
${code}
\`\`\``,
  tests: (code, file) => `Write a single Jest test file for the following TS/TSX, targeting ≥70% coverage. Return ONLY the test content inside one code fence.
File: ${file}
\`\`\`typescript
${code}
\`\`\``,
  review: (code, file) => `Review this TS/TSX for CFH standards (@ imports, no any, strict types). If changes are needed, return the FULL corrected file; else reply "OK".
File: ${file}
\`\`\`typescript
${code}
\`\`\``,
  arbitrate: (text, file, reason) => `Arbitrate this decision: ${reason}. If code needs fixes, return the FULL corrected file; else return the original content.
Context/File: ${file}
\`\`\`
${text}
\`\`\``,
  evaluate: (code, file) => `Evaluate TS/TSX for CFH standards. If updates are required, return FULL corrected file; else reply "NO-OP".
File: ${file}
\`\`\`typescript
${code}
\`\`\``,
};

const askAI = async (modelName, prompt, apiKey) => {
  try {
    const { text } = await generateText({
      model: modelName || "openai:gpt-4o-mini",
      apiKey,
      prompt,
      maxTokens: 2000,
      temperature: 0.2,
    });
    return text || "";
  } catch {
    const key = apiKey;
    if (!key) return "";
    const res = await fetch("https://api.openai.com/v1/chat/completions", {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "gpt-4o-mini",
        messages: [{ role: "user", content: prompt }],
        temperature: 0.2, max_tokens: 2000,
      }),
    });
    if (!res.ok) return "";
    const data = await res.json();
    return data?.choices?.[0]?.message?.content || "";
  }
};

(async () => {
  try {
    const raw = await readStdin();
    const inp = JSON.parse(raw || "{}");
    const { op, file_path, code, extra, env } = inp;
    const apiKey = (env?.OPENAI_API_KEY || env?.SPARKA_API_KEY || process.env.OPENAI_API_KEY || "").trim();
    if (!op || !apiKey) return void process.stdout.write("");
    const prompt = op === "arbitrate"
      ? prompts.arbitrate(code || "", file_path || "unknown", extra?.reason || "N/A")
      : prompts[op](code || "", file_path || "unknown");
    const out = await askAI("openai:gpt-4o-mini", prompt, apiKey);
    process.stdout.write(out || "");
  } catch {
    process.stdout.write("");
  }
})();
