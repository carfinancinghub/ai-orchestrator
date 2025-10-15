from __future__ import annotations

import json
import os
import re
import subprocess
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Optional deps: Gemini primary; we soft-import fallbacks
try:
    import google.generativeai as genai
except Exception:
    genai = None

# (Optional fallback SDK stubs; you can wire real ones later)
try:
    import openai  # type: ignore
except Exception:
    openai = None

# Constants
REPO_ROOT = Path(os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend"))
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "reports"))
MODEL_GEMINI = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")
GEMINI_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
MAX_FILES_PER_BATCH = int(os.getenv("REVIEW_BATCH_MAX", "25"))
MAX_OUTPUT_TOKENS = int(os.getenv("REVIEW_MAX_TOKENS", "1500"))

LANG_MAP = {
    ".tsx": "TypeScript React",
    ".ts": "TypeScript",
    ".jsx": "JavaScript React",
    ".js": "JavaScript",
    ".css": "CSS",
    ".json": "JSON",
}

HEAD_BYTES = 32_000  # cap per file to keep prompts small

MOVE_BLOCK_RE = re.compile(r"```json\s*?\{.*?\"moves\"\s*?:.*?\}\s*```", re.S | re.I)


@dataclass
class ReviewMove:
    dest: str
    confidence: float
    reason: str


def _read_head(path: str) -> str:
    p = Path(path)
    try:
        data = p.read_bytes()[:HEAD_BYTES]
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return data.decode("latin-1", errors="replace")
    except Exception as e:
        return f"/* read error: {e!r} */"


def _rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT)).replace("\\", "/")
    except Exception:
        return p.as_posix()


def review_file(path: str, repo_root: Optional[str] = None) -> Dict[str, Any]:
    """
    Legacy single-file heuristic (kept so /convert/tree UI doesn't break).
    Produces a minimal "routing" with a dummy move so the caller stays happy.
    """
    p = Path(path)
    rel = _rel(p)
    ext = p.suffix.lower()
    dest = "buyer" if "buyer" in rel.lower() else "common"
    conf = 0.85 if dest == "buyer" else 0.1
    md = textwrap.dedent(
        f"""\
        # {p.name}

        **Detected Type:** `{ext or "unknown"}`  |  **Suggested Dest:** `{dest}`  |  **Confidence:** `{conf:.2f}`

        ## Purpose (heuristic)
        - Lightweight legacy pass; LLM batch reviewer supersedes this.

        ## Code Preview
        ```
        {_read_head(path)[:800]}
        ```
        """
    )
    return {
        "routing": {
            "suggested_moves": [{"dest": str((REPO_ROOT / f"components/{dest}/{p.name}")), "confidence": conf}]
        },
        "markdown": md,
    }


def _render_prompt(files: List[Path], tier: str = "free") -> str:
    tmpl_path = Path("prompts/gemini_batch_review.md")
    if not tmpl_path.exists():
        raise FileNotFoundError("prompts/gemini_batch_review.md is missing")

    tmpl = tmpl_path.read_text(encoding="utf-8")

    # Build files_block: a compact list of snippets
    parts: List[str] = []
    for fp in files:
        rel = _rel(fp)
        ext = fp.suffix.lower().lstrip(".")
        head = _read_head(str(fp))
        parts.append(
            textwrap.dedent(
                f"""\
                ---
                ### File: `{rel}`
                ```{ext or 'text'}
                {head}
                ```
                """
            )
        )
    files_block = "\n".join(parts)

    # Prefer jinja2 if available
    rendered = None
    try:
        from jinja2 import Template  # type: ignore

        rendered = Template(tmpl).render(
            review_tier=tier,
            files_block=files_block,
        )
    except Exception:
        # Simple fallback replacing only the two placeholders used above
        rendered = (
            tmpl.replace("{{review_tier|default(\"free\")}}", tier)
            .replace("{{review_tier}}", tier)
            .replace("{{files_block}}", files_block)
        )

    return rendered


def _call_gemini(prompt: str) -> str:
    if not genai or not GEMINI_KEY:
        raise RuntimeError("Gemini SDK/key unavailable")
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(MODEL_GEMINI)
    resp = model.generate_content(
        prompt,
        generation_config={"max_output_tokens": MAX_OUTPUT_TOKENS},
        safety_settings=None,
        request_options={"timeout": 30},
    )
    return getattr(resp, "text", "").strip()


def _extract_moves_blocks(markdown: str) -> List[Dict[str, Any]]:
    """
    Find all fenced JSON blocks that contain a 'moves' array and parse them.
    Returns a list of dicts like {"path": "...", "moves":[...]}.
    """
    results: List[Dict[str, Any]] = []
    for m in MOVE_BLOCK_RE.finditer(markdown):
        block = m.group(0)
        json_text = re.sub(r"^```json|```$", "", block.strip(), flags=re.I | re.M).strip()
        try:
            obj = json.loads(json_text)
            if isinstance(obj, dict) and "moves" in obj:
                results.append(obj)
        except Exception:
            continue
    return results


def review_batch(
    file_paths: List[str],
    *,
    tier: str = "free",
    label: Optional[str] = None,
    reports_dir: Path = REPORTS_DIR,
) -> Dict[str, Any]:
    """
    LLM batch review (Gemini primary, soft-fallback to heuristics).
    Writes a single batch .md and returns parsed moves + per-file mini .mds.
    """
    if not file_paths:
        return {"ok": False, "error": "no_files"}

    files = [Path(p) for p in file_paths][:MAX_FILES_PER_BATCH]
    prompt = _render_prompt(files, tier=tier)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_dir = reports_dir / (label or "")
    batch_dir.mkdir(parents=True, exist_ok=True)

    batch_md = batch_dir / f"batch_review_{stamp}.md"

    llm_text = ""
    try:
        llm_text = _call_gemini(prompt)
    except Exception as e:
        # Fallback: stitch a minimal markdown with heuristic headers
        heads = []
        for fp in files:
            rel = _rel(fp)
            ext = fp.suffix.lower()
            heads.append(
                f"### File: `{rel}`\n\n```{ext or 'text'}\n{_read_head(str(fp))[:600]}\n```\n"
            )
        llm_text = (
            f"# Fallback Heuristic Batch Review — {tier}\n\n"
            "Gemini unavailable; produced a basic pass.\n\n" + "\n".join(heads)
        )

    batch_md.write_text(llm_text, encoding="utf-8")

    # Parse JSON move blocks from the markdown
    parsed = _extract_moves_blocks(llm_text)

    # Per-file mini .mds (handy to attach on PRs)
    per_file_paths: List[str] = []
    for obj in parsed:
        rel = obj.get("path") or ""
        safe = rel.replace("/", "__").replace("\\", "__")
        mini = batch_dir / f"{safe}_review.md"
        mini.write_text(
            textwrap.dedent(
                f"""\
                # Review — {rel}

                ```json
                {json.dumps(obj, ensure_ascii=False, indent=2)}
                ```
                """
            ),
            encoding="utf-8",
        )
        per_file_paths.append(str(mini))

    return {
        "ok": True,
        "batch_md": str(batch_md),
        "per_file_mds": per_file_paths,
        "moves": parsed,
    }


# Optional utility you can call from routes to get a git diff file list
def get_changed_files(base_ref: str, cwd: Path) -> List[str]:
    """
    Returns paths changed vs base_ref (e.g., 'origin/main' or a SHA).
    """
    try:
        out = subprocess.check_output(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            cwd=str(cwd),
            stderr=subprocess.DEVNULL,
        )
        lines = out.decode("utf-8", errors="replace").splitlines()
        return [l.strip() for l in lines if l.strip()]
    except Exception:
        return []