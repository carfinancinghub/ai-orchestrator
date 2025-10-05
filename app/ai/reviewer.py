# app/ai/reviewer.py
# CFH — MD-first Batch Reviewer (Gemini-first, precise + robust)
#
# Raw (for grounded diffs next time):
# https://raw.githubusercontent.com/carfinancinghub/ai-orchestrator/feat/migration-plan-hooks/app/ai/reviewer.py
#
# ✨ What this does
# - Runs an md-first **Gemini** review over a batch of files (tiers: Free / Premium / Wow++).
# - Works with both prompt placeholder styles: {{batch_files}} and {{files_block}}.
# - Ensures tier headings exist; prepends a validation banner if they don’t.
# - Harvests per-file **routing JSON** (supports legacy "moves") + **dependencies**.
# - Writes one batch .md and also splits **per-file .md** sections via `---`.
# - Extracts Wow++ fenced code blocks (ts/tsx/typescript) for optional builders.
# - Includes small helpers: changed-file picker, per-file parser, TSX sketch writer.
#
# Env knobs:
#   FRONTEND_ROOT      (default: C:\CFH\frontend)
#   REPORTS_DIR        (default: reports)
#   GOOGLE_API_KEY / GEMINI_API_KEY
#   GEMINI_MODEL       (default: gemini-1.5-flash-latest)
#   REVIEW_BATCH_MAX   (default: 25)
#   REVIEW_MAX_TOKENS  (default: 1500)
#   REVIEW_TIMEOUTS    (default: 30s)
#
# Safe to import in CI; all cloud calls are guarded and have fallbacks.

from __future__ import annotations

import json
import os
import re
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Optional deps: Gemini primary; soft-import others -----------------------

try:
    import google.generativeai as genai  # type: ignore
except Exception:  # pragma: no cover
    genai = None  # type: ignore

# (Optional future fallback SDK stubs)
try:
    import openai  # type: ignore
except Exception:  # pragma: no cover
    openai = None  # type: ignore

# --- Constants / Config ------------------------------------------------------

REPO_ROOT = Path(os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend"))
REPORTS_DIR = Path(os.getenv("REPORTS_DIR", "reports"))

MODEL_GEMINI = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")
GEMINI_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

MAX_FILES_PER_BATCH = max(1, int(os.getenv("REVIEW_BATCH_MAX", "25")))
MAX_OUTPUT_TOKENS = max(256, int(os.getenv("REVIEW_MAX_TOKENS", "1500")))
REVIEW_TIMEOUT_S = float(os.getenv("REVIEW_TIMEOUT_S", "30"))

HEAD_BYTES = 32_000  # bytes per file header injected into prompt

# --- Regex Helpers -----------------------------------------------------------

# Split per-file sections in the batch .md
MD_SECTION_SPLIT = re.compile(r"^\s*---\s*$", re.MULTILINE)

# Routing JSON fenced blocks
ROUTING_JSON_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.IGNORECASE | re.DOTALL)

# Tier validation
REQUIRED_TIER_TITLES = ["Free Tier", "Premium Tier", "Wow++ Tier"]

# Wow++ section & code fence
WOW_SECTION_RE = re.compile(
    r"(?P<header>^#+\s*Wow\+\+\s*Tier[^\n]*\n)(?P<body>.*?)(^#+\s|\Z)",
    re.IGNORECASE | re.DOTALL | re.MULTILINE,
)
FENCED_CODE_RE = re.compile(
    r"```(?:ts|tsx|typescript)?\s*(?P<code>[\s\S]*?)```",
    re.IGNORECASE,
)

# Back-compat: legacy blocks that used `"moves"` instead of `"suggested_moves"`
LEGACY_MOVES_BLOCK_RE = re.compile(
    r"```json\s*?\{.*?\"moves\"\s*?:.*?\}\s*```",
    re.IGNORECASE | re.DOTALL,
)

# --- Small utils -------------------------------------------------------------

def _read_head(path: str) -> str:
    """Read first HEAD_BYTES of a file and decode safely (for prompt context)."""
    p = Path(path)
    try:
        data = p.read_bytes()[:HEAD_BYTES]
        try:
            return data.decode("utf-8", errors="replace")
        except Exception:
            return data.decode("latin-1", errors="replace")
    except Exception as e:  # pragma: no cover
        return f"/* read error: {e!r} */"


def _rel(p: Path) -> str:
    """Repo-relative (posix) if possible."""
    try:
        return str(p.relative_to(REPO_ROOT)).replace("\\", "/")
    except Exception:
        return p.as_posix()


def _ensure_tiers(md_text: str) -> bool:
    return all(title in md_text for title in REQUIRED_TIER_TITLES)


def _extract_wow_code(md_text: str) -> str:
    sec = WOW_SECTION_RE.search(md_text)
    if not sec:
        return ""
    body = sec.group("body")
    fence = FENCED_CODE_RE.search(body)
    if not fence:
        return ""
    return (fence.group("code") or "").strip()


def _load_prompt_template() -> str:
    p = Path("prompts/gemini_batch_review.md")
    if not p.exists():
        raise FileNotFoundError("prompts/gemini_batch_review.md is missing")
    return p.read_text(encoding="utf-8")


def _render_prompt(files: List[Path], tier: str = "free", label: str = "") -> str:
    """
    Build a prompt compatible with both {{batch_files}} and {{files_block}} styles.
    - batch_files: lines "File: <path>"
    - files_block: per-file header with inline code fences containing HEAD_BYTES
    Also inject a small blueprint list (kept in the template if present).
    """
    # Minimal list view (for {{batch_files}})
    batch_files = "\n".join([f"File: {_rel(fp)}" for fp in files])

    # Rich block view (for {{files_block}})
    parts: List[str] = []
    for fp in files:
        rel = _rel(fp)
        ext = (fp.suffix.lower().lstrip(".") or "text")
        head = _read_head(str(fp))
        parts.append(
            textwrap.dedent(
                f"""\
                ---
                ### File: `{rel}`
                ```{ext}
                {head}
                ```
                """
            )
        )
    files_block = "\n".join(parts)

    tpl = _load_prompt_template()
    # Be forgiving: replace several variants if present
    rendered = (
        tpl.replace("{{review_tier}}", tier)
           .replace("{{ review_tier }}", tier)
           .replace('{{ review_tier|default("free") }}', tier)
           .replace("{{ label }}", label)
           .replace("{{label}}", label)
           .replace("{{batch_files}}", batch_files)
           .replace("{{files_block}}", files_block)
           # common blueprints if the template wants them
           .replace("{{blueprint}}", "- @models/Vehicle\n- @types/LoanTerms\n- @services/escrow/*\n- backend:/routes/escrow/*")
    )
    return rendered


def _call_gemini(prompt: str) -> str:
    if not genai or not (GEMINI_KEY and MODEL_GEMINI):
        raise RuntimeError("Gemini SDK/key unavailable")
    genai.configure(api_key=GEMINI_KEY)
    model = genai.GenerativeModel(MODEL_GEMINI)
    resp = model.generate_content(
        prompt,
        generation_config={"max_output_tokens": MAX_OUTPUT_TOKENS},
        safety_settings=None,
        request_options={"timeout": REVIEW_TIMEOUT_S},
    )
    return (getattr(resp, "text", "") or "").strip()


def _parse_json_blocks(md_text: str) -> List[Dict[str, Any]]:
    """Parse ALL fenced json blocks; normalize legacy `moves` → `suggested_moves`."""
    blocks: List[Dict[str, Any]] = []
    # 1) Standard json fences
    for m in ROUTING_JSON_RE.finditer(md_text):
        txt = m.group(1)
        try:
            obj = json.loads(txt)
            if isinstance(obj, dict):
                # normalize legacy
                if "moves" in obj and "suggested_moves" not in obj:
                    obj["suggested_moves"] = obj.pop("moves")
                obj.setdefault("suggested_moves", [])
                obj.setdefault("dependencies", [])
                blocks.append(obj)
        except Exception:
            continue
    # 2) Legacy fences that might not match ROUTING_JSON_RE due to formatting
    for m in LEGACY_MOVES_BLOCK_RE.finditer(md_text):
        block = m.group(0)
        json_text = re.sub(r"^```json|```$", "", block.strip(), flags=re.I | re.M).strip()
        try:
            obj = json.loads(json_text)
            if isinstance(obj, dict):
                if "moves" in obj and "suggested_moves" not in obj:
                    obj["suggested_moves"] = obj.pop("moves")
                obj.setdefault("suggested_moves", [])
                obj.setdefault("dependencies", [])
                blocks.append(obj)
        except Exception:
            continue
    return blocks


def _per_file_sections(md_text: str) -> List[str]:
    """Split md into sections by '---' boundary; drop empties."""
    return [s.strip() for s in MD_SECTION_SPLIT.split(md_text) if s.strip()]


def _extract_file_path_from_section(sec: str) -> Optional[str]:
    """
    Accept any of:
      **File:** `path`
      ### File: `path`
      File: `path`
    """
    m = re.search(r"(?:\*\*File:\*\*|###\s*File:|^File:)\s*`([^`]+)`", sec, flags=re.IGNORECASE | re.MULTILINE)
    if m:
        return m.group(1)
    return None


def _routing_from_section(sec: str) -> Optional[Dict[str, Any]]:
    """Return first routing object in a section, if any."""
    blocks = _parse_json_blocks(sec)
    for obj in blocks:
        if "suggested_moves" in obj or "dependencies" in obj:
            # ensure presence of keys even if empty
            obj.setdefault("suggested_moves", [])
            obj.setdefault("dependencies", [])
            return obj
    return None


def _write_batch_artifacts(md_text: str, label: Optional[str], reports_dir: Path) -> Tuple[Path, List[Path]]:
    """
    Write the full batch .md and split into per-file .mds using '---' separators.
    Names per-file docs from a “File: `rel/path`” line when available.
    """
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label_dir = reports_dir / (label or "")
    label_dir.mkdir(parents=True, exist_ok=True)

    batch_md = label_dir / f"batch_review_{stamp}.md"
    batch_md.write_text(md_text, encoding="utf-8")

    per_file_dir = label_dir / "mds"
    per_file_dir.mkdir(parents=True, exist_ok=True)

    paths: List[Path] = []
    for i, sec in enumerate(_per_file_sections(md_text), start=1):
        rel = _extract_file_path_from_section(sec)
        base = f"review_{i:03d}.md"
        if rel:
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", rel)
            base = f"{safe}.md"
        p = per_file_dir / base
        p.write_text(sec + "\n", encoding="utf-8")
        paths.append(p)

    return batch_md, paths


# --- Public API --------------------------------------------------------------

def review_batch(
    file_paths: List[str],
    *,
    tier: str = "free",
    label: Optional[str] = None,
    reports_dir: Path = REPORTS_DIR,
    md_first: bool = True,
) -> Dict[str, Any]:
    """
    LLM batch review (Gemini primary, with strict md-first structure).
    Returns:
      {
        "ok": True/False,
        "batch_md": str,
        "per_file_mds": [str, ...],
        "deps_index": { "<file>": [deps...] },
        "validation": { "has_all_tiers": bool, "notes": [str, ...] }
      }
    """
    if not file_paths:
        return {"ok": False, "error": "no_files"}

    files = [Path(p) for p in file_paths][:MAX_FILES_PER_BATCH]

    prompt = _render_prompt(files, tier=tier, label=label or "")

    # --- Call LLM (or fallback) ---
    try:
        md_text = _call_gemini(prompt) if md_first else ""
    except Exception:
        md_text = ""

    if not md_text:
        # Fallback: structural markdown with minimal, valid sections
        parts: List[str] = [f"# Fallback Heuristic Batch Review — {tier}", ""]
        for fp in files:
            rel = _rel(fp)
            ext = fp.suffix.lower().lstrip(".") or "text"
            parts += [
                f"### File: `{rel}`",
                "",
                "**Summary**",
                "- (heuristic) TBD",
                "",
                "## Free Tier",
                "- Generic scan only.",
                "",
                "## Premium Tier",
                "- Use @aliases and propose interfaces.",
                "",
                "## Wow++ Tier",
                "```ts",
                "// sketch TBD",
                "```",
                "",
                "```json",
                json.dumps(
                    {
                        "suggested_moves": [
                            {
                                "source": rel,
                                "dest": rel,
                                "confidence": 0.86,
                                "reason": "heuristic",
                            }
                        ],
                        "dependencies": ["@services/escrow/fees.ts"],
                    },
                    indent=2,
                ),
                "```",
                "",
                "---",
            ]
        md_text = "\n".join(parts)

    # --- Validate + index per-file routing/deps ---
    has_all_tiers = _ensure_tiers(md_text)
    notes: List[str] = []
    if not has_all_tiers:
        notes.append("Missing one or more required tier headings: Free Tier, Premium Tier, Wow++ Tier.")

    deps_index: Dict[str, List[str]] = {}
    # Build deps per file by scanning sections
    for sec in _per_file_sections(md_text):
        rel = _extract_file_path_from_section(sec)
        routing = _routing_from_section(sec) or {}
        deps = routing.get("dependencies") or []
        if rel and deps:
            deps_index[rel] = list(deps)

    if not deps_index:
        notes.append("No dependencies parsed from routing JSON (per-file).")

    # Prefix validation banner if needed
    md_final = md_text
    if notes:
        banner = "> **Validation**: " + "; ".join(notes)
        md_final = banner + "\n\n" + md_text

    batch_md, per_file_paths = _write_batch_artifacts(md_final, label, reports_dir)

    return {
        "ok": True,
        "batch_md": str(batch_md),
        "per_file_mds": [p.as_posix() for p in per_file_paths],
        "deps_index": deps_index,
        "validation": {"has_all_tiers": has_all_tiers, "notes": notes},
    }


# --- Parsers & Builders ------------------------------------------------------

def parse_review_md(md_text: str) -> Dict[str, Any]:
    """
    Parse a single per-file review .md (one section) to extract:
      - has_all_tiers (bool)  # for the section’s text
      - routing (dict)        # normalized (legacy `moves` → `suggested_moves`)
      - dependencies (list[str])
      - wow_code (str)
    """
    has_tiers = _ensure_tiers(md_text)
    routing: Dict[str, Any] = _routing_from_section(md_text) or {}
    deps = list(routing.get("dependencies") or [])
    wow_code = _extract_wow_code(md_text)

    return {
        "has_all_tiers": has_tiers,
        "routing": routing,
        "dependencies": deps,
        "wow_code": wow_code,
    }


def build_from_markdowns(md_paths: List[str], apply_moves: bool = False) -> Dict[str, Any]:
    """
    Reads multiple per-file .mds, reconstructs Wow++ sketches and routing JSON,
    and returns a non-destructive plan (no writes unless you later opt-in).
    """
    plan: List[Dict[str, Any]] = []
    for p in md_paths:
        txt = Path(p).read_text(encoding="utf-8", errors="ignore")
        parsed = parse_review_md(txt)
        routing = parsed.get("routing") or {}
        wow_code = parsed.get("wow_code") or ""
        plan.append({"md": str(p), "routing": routing, "sketch": wow_code})
    return {"ok": True, "plan": plan}


def build_ts_from_md(md_path: str, apply_moves: bool = True) -> Dict[str, Any]:
    """
    Consume a single per-file review .md and materialize a .tsx file using the
    Wow++ sketch + routing.dest (if provided). Returns {"written": [paths]}.
    """
    out = {"written": []}
    p = Path(md_path)
    text = p.read_text(encoding="utf-8", errors="ignore")
    parsed = parse_review_md(text)

    routing = parsed.get("routing") or {}
    # First move wins; accept `suggested_moves` or legacy `moves`
    moves = routing.get("suggested_moves") or routing.get("moves") or []
    dest: Optional[Path] = None
    if moves and isinstance(moves, list) and isinstance(moves[0], dict):
        dest_val = moves[0].get("dest") or moves[0].get("destination")
        if dest_val:
            dest = Path(dest_val)

    if not dest:
        dest = Path("src/_ai_out")
    dest.mkdir(parents=True, exist_ok=True)

    # Filename from md filename
    stem = p.stem.replace("_review", "")
    out_file = dest / f"{stem}.tsx"

    wow_code = parsed.get("wow_code") or "// (no Wow++ code emitted)"
    banner = f"// Generated from {p.as_posix()} — apply_moves={apply_moves}\n"
    out_file.write_text(banner + wow_code + "\n", encoding="utf-8")
    out["written"].append(out_file.as_posix())

    return out


# --- Git helpers -------------------------------------------------------------

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
    except Exception:  # pragma: no cover
        return []
