# app/ai/gemini_mdgen.py
from __future__ import annotations
import os, json, yaml
from pathlib import Path
from typing import List, Dict, Any, Optional

def use_gemini() -> bool:
    return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))

def generate_md_for_files(
    paths: List[str],
    tier: str,
    blueprint_hint: str = "Auctions: Bid + escrow",
    prompts_path: str = "prompts/gemini_5step.md",
) -> Dict[str, Any]:
    """
    Returns dict:
      {
        "per_file_mds": [ "reports/.../fileA.plan.md", ... ],
        "batch_md": "reports/.../AuctionModule.md",
        "dependencies": {}
      }
    """
    out: Dict[str, Any] = {"per_file_mds": [], "dependencies": {}}
    reports_dir = Path(os.getenv("REPORTS_DIR", "reports"))
    label = "auctions"
    out_dir = reports_dir / "plans" / label
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- Gemini call (minimal, robust fallback) ---
    if not use_gemini():
        # Fallback: write a tiny md per file with schema header only
        for p in paths:
            name = Path(p).name.replace("/", "_")
            md = out_dir / f"{name}.plan.md"
            md.write_text(
                "# md-first (fallback)\n\n```yaml\nfunctions: []\ntypes: []\ndependencies: []\nintegrates_with: []\nplan: []\n```\n",
                encoding="utf-8",
            )
            out["per_file_mds"].append(md.as_posix())
        out["batch_md"] = (out_dir / "AuctionModule.md").as_posix()
        Path(out["batch_md"]).write_text("# AuctionModule (fallback)\n", encoding="utf-8")
        return out

    import google.generativeai as genai  # type: ignore
    genai.configure(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    model = genai.GenerativeModel("gemini-flash-latest")

    prompt_base = Path(prompts_path).read_text(encoding="utf-8")
    # Keep the call extremely simple and deterministic; iterate small batches
    for p in paths:
        text = Path(p).read_text(encoding="utf-8", errors="ignore")[:20000]
        user = f"{prompt_base}\n\nTier: {tier}\nBlueprint: {blueprint_hint}\n\nSource file: {p}\n\n---\n<BEGIN SOURCE>\n{text}\n<END SOURCE>\n\nWrite the `.md-first` output now."
        resp = model.generate_content(user)
        md = resp.text or "# (empty)"
        name = Path(p).name.replace("/", "_")
        md_path = out_dir / f"{name}.plan.md"
        md_path.write_text(md, encoding="utf-8")
        out["per_file_mds"].append(md_path.as_posix())
    # A simple batch file
    batch = out_dir / "AuctionModule.md"
    batch.write_text("# Auction Module – Batch\n\n(see per-file .mds in this folder)\n", encoding="utf-8")
    out["batch_md"] = batch.as_posix()
    return out