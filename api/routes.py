# --- inside api/routes.py ---

class ConvertTreeReq(BaseModel):
    root: str = "src"
    dry_run: bool = True
    batch_cap: int = 25
    # NEW:
    label: Optional[str] = None
    review_tier: str = "free"           # free | premium | wow
    generate_mds: bool = False          # force batch .mds even when dry_run=True
    git_diff_base: Optional[str] = None # e.g., "origin/main" or a SHA

# ... keep your helpers & constants ...

@router.post("/convert/tree", tags=["convert"], name="convert_tree")
def convert_tree(req: ConvertTreeReq = Body(...)) -> dict:
    root = Path(req.root)
    converted: List[str] = []
    skipped: List[str] = []
    reviews: List[Dict[str, Any]] = []

    # collect and filter (same as your current code) ...
    if root.exists() and root.is_dir():
        all_items = list(root.rglob("*"))
        items: List[Path] = []
        for p in all_items:
            if _is_noise(p):
                continue
            items.append(p)

        for p in items[:200]:
            (converted if p.is_file() else skipped).append(str(p).replace("\\", "/"))

        cap = max(0, int(req.batch_cap))
        code_files = [p for p in items if p.is_file() and p.suffix.lower() in CODE_EXTS]

        # NEW: git-diff filter (best-effort)
        if req.git_diff_base:
            from app.ai.reviewer import get_changed_files  # lazy import
            changed = set(get_changed_files(req.git_diff_base, cwd=Path.cwd()))
            code_files = [p for p in code_files if _rel(p) in changed]

        # legacy per-file mini review to keep JSON response stable
        for p in code_files[:cap]:
            try:
                r = review_file(
                    str(p),
                    repo_root=os.getenv("FRONTEND_ROOT", r"C:\CFH\frontend"),
                )
                reviews.append(
                    {
                        "file": str(p).replace("\\", "/"),
                        "routing": r["routing"],
                        "markdown": r["markdown"],
                    }
                )
            except Exception as e:
                reviews.append(
                    {
                        "file": str(p).replace("\\", "/"),
                        "error": repr(e),
                        "routing": {"suggested_moves": []},
                        "markdown": "",
                    }
                )

    resp: Dict[str, Any] = {
        "ok": True,
        "root": str(root),
        "dry_run": req.dry_run,
        "converted": converted,
        "skipped": skipped,
        "reviews_count": len(reviews),
        "reviews": reviews,
        "artifacts": {},
        "label": req.label or "",
    }

    # Save JSON artifact (unchanged from your version)
    reports_dir = Path(os.getenv("REPORTS_DIR", "reports"))
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = reports_dir / (f"{req.label}/" if req.label else "") / f"convert_dryrun_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        out.write_text(json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8")
        resp["artifact"] = str(out)
    except Exception as e:
        resp["artifact_error"] = repr(e)

    # Markdown summary (kept from your version)
    try:
        summary_path = out.with_suffix(".summary.md")
        lines: List[str] = []
        lines.append(f"# Convert Dry-Run Summary — {stamp}\n")
        lines.append(f"- Root: `{resp['root']}`")
        lines.append(f"- Dry run: `{resp['dry_run']}`")
        lines.append(f"- Reviews: `{resp['reviews_count']}`")
        lines.append(f"- Converted listed: `{len(resp['converted'])}`  • Skipped listed: `{len(resp['skipped'])}`\n")

        TOP = min(10, len(reviews))
        if TOP:
            lines.append("## Top Reviewed Files\n")
            for r in reviews[:TOP]:
                file = r.get("file", "")
                moves = r.get("routing", {}).get("suggested_moves", [])
                if moves:
                    dest = moves[0].get("dest", "")
                    conf = moves[0].get("confidence", "")
                    lines.append(f"- `{file}` → `{dest}` (conf: {conf})")
                else:
                    lines.append(f"- `{file}` (no suggestion)")

        summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        resp["summary"] = str(summary_path)
    except Exception as e:
        resp["summary_error"] = repr(e)

    # NEW: auto batch .md generation
    try:
        should_batch = (not req.dry_run) or bool(req.generate_mds)
        if should_batch:
            from app.ai.reviewer import review_batch  # lazy import

            # Decide candidate set (use same filtered list)
            candidates = [Path(p) for p in converted if p.endswith((".ts", ".tsx", ".js", ".jsx"))]
            # Fall back to reviews[] list if converted is truncated:
            if not candidates and reviews:
                candidates = [Path(r["file"]) for r in reviews]

            candidates = candidates[:max(1, int(req.batch_cap))]
            batch = review_batch(
                [str(p) for p in candidates],
                tier=req.review_tier,
                label=req.label,
                reports_dir=reports_dir,
            )
            resp["artifacts"] = {
                "mds": batch.get("per_file_mds", []),
                "batch_md": batch.get("batch_md"),
            }
    except Exception as e:
        resp.setdefault("errors", []).append({"where": "batch_mds", "error": repr(e)})

    return resp
