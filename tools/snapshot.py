
"""
Path: tools/snapshot.py
Directory Snapshot Utility — generates JSON/Markdown tree under reports/.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# ---------- Models ----------
@dataclass
class FileInfo:
    rel_path: str
    size: int
    mtime: str
    ext: str
    line_count: Optional[int] = None
    preview: Optional[str] = None
    sha256: Optional[str] = None


@dataclass
class Snapshot:
    root: str
    generated_at: str
    total_files: int
    total_dirs: int
    total_bytes: int
    by_extension: Dict[str, Dict[str, int]]
    files: List[FileInfo] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "root": self.root,
            "generated_at": self.generated_at,
            "total_files": self.total_files,
            "total_dirs": self.total_dirs,
            "total_bytes": self.total_bytes,
            "by_extension": self.by_extension,
            "files": [fi.__dict__ for fi in self.files],
        }


# ---------- Helpers ----------
TEXT_EXTS = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".ini", ".cfg", ".toml",
    ".csv", ".tsv", ".gitignore", ".env", ".log", ".xml", ".html", ".css", ".js", ".ts",
}

DEFAULT_EXCLUDES = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
    "artifacts_quarantine", "dist", "build", "reports", "*.egg-info",
    # Common noisy/python runtime dirs (case-insensitive)
    "Lib", "site-packages", "Scripts", "Include",
}


def human_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    s = float(n)
    for u in units:
        if s < 1024.0:
            return f"{s:.1f}{u}"
        s /= 1024.0
    return f"{s:.1f}PB"


def should_exclude(path: Path, excludes: Iterable[str]) -> bool:
    """Case-insensitive, path-aware exclude check."""
    import fnmatch

    pstr = str(path).replace("\\", "/").lower()
    name = path.name.lower()
    parts_lower = {part.lower() for part in path.parts}
    for ex in excludes:
        exl = ex.replace("\\", "/").lower()
        exl_stripped = exl.strip("*")
        if exl in parts_lower:
            return True
        if fnmatch.fnmatch(name, exl):
            return True
        if exl_stripped and exl_stripped in pstr:
            return True
    return False


def safe_text_preview(p: Path, max_bytes: int) -> Tuple[Optional[str], Optional[int]]:
    try:
        with p.open("rb") as f:
            data = f.read(max_bytes)
        text = data.decode("utf-8", errors="replace")
        lines = text.replace("\r\n", "\n").replace("\r", "\n").splitlines()
        return ("\n".join(lines[:50]), len(lines))
    except Exception:
        return None, None


def compute_sha256(p: Path) -> Optional[str]:
    try:
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


def build_tree_md(root: Path, files: List[FileInfo]) -> str:
    tree: Dict[str, Dict[str, object]] = {}
    for fi in files:
        parts = Path(fi.rel_path).parts
        cur = tree
        for part in parts[:-1]:
            cur = cur.setdefault(part, {"__size__": 0, "__children__": {}})["__children__"]  # type: ignore
        # accumulate sizes
        cur2 = tree
        for part in parts[:-1]:
            cur2 = cur2.setdefault(part, {"__size__": 0, "__children__": {}})  # type: ignore
            cur2["__size__"] = int(cur2.get("__size__", 0)) + fi.size  # type: ignore
        # record file
        leaf_parent = tree
        for part in parts[:-1]:
            leaf_parent = leaf_parent[part]["__children__"]  # type: ignore
        leaf_parent.setdefault("__files__", []).append((parts[-1], fi.size))  # type: ignore

    def render(node: Dict[str, object], prefix: str = "") -> List[str]:
        lines: List[str] = []
        for name in sorted(k for k in node.keys() if not k.startswith("__")):
            child = node[name]  # type: ignore
            size = child.get("__size__", 0)  # type: ignore
            lines.append(f"{prefix}📁 {name} ({human_size(int(size))})")
            lines.extend(render(child["__children__"], prefix + "    "))  # type: ignore
            files_here = child.get("__files__", [])  # type: ignore
            for fname, fsize in sorted(files_here):
                lines.append(f"{prefix}    📄 {fname} ({human_size(int(fsize))})")
        return lines

    md = ["# Snapshot Tree\n"]
    md.extend(render(tree))
    return "\n".join(md) + "\n"


def collect_snapshot(root: Path, excludes: Iterable[str], max_preview_bytes: int, hashes: bool) -> Snapshot:
    root = root.resolve()
    total_files = 0
    total_dirs = 0
    total_bytes = 0
    files: List[FileInfo] = []
    by_ext: Dict[str, Dict[str, int]] = {}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_exclude(Path(dirpath) / d, excludes)]
        total_dirs += 1
        for fname in filenames:
            p = Path(dirpath) / fname
            if should_exclude(p, excludes):
                continue
            try:
                st = p.stat()
            except FileNotFoundError:
                continue
            size = int(st.st_size)
            total_files += 1
            total_bytes += size
            rel = str(p.relative_to(root))
            ext = p.suffix.lower() or "<none>"
            mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
            preview, line_count = (None, None)
            if ext in TEXT_EXTS and size <= max_preview_bytes:
                preview, line_count = safe_text_preview(p, max_preview_bytes)
            sha256 = compute_sha256(p) if hashes else None

            files.append(FileInfo(rel, size, mtime, ext, line_count, preview, sha256))
            ext_bucket = by_ext.setdefault(ext, {"files": 0, "bytes": 0})
            ext_bucket["files"] += 1
            ext_bucket["bytes"] += size

    return Snapshot(
        root=str(root),
        generated_at=datetime.now(timezone.utc).isoformat(),
        total_files=total_files,
        total_dirs=total_dirs,
        total_bytes=total_bytes,
        by_extension=by_ext,
        files=files,
    )


def write_outputs(root: Path, snap: Snapshot) -> tuple[Path, Path]:
    reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = reports_dir / f"snap-{ts}.json"
    md_path = reports_dir / f"snap-{ts}.md"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(snap.to_dict(), f, indent=2)

    md = [
        f"# Snapshot Report ({snap.generated_at})\n",
        f"Root: `{snap.root}`\n\n",
        f"- Total files: {snap.total_files}\n",
        f"- Total dirs: {snap.total_dirs}\n",
        f"- Total bytes: {snap.total_bytes} ({human_size(snap.total_bytes)})\n",
        "\n## By extension\n",
    ]
    for ext, stats in sorted(snap.by_extension.items(), key=lambda kv: kv[0]):
        md.append(f"- `{ext}`: {stats['files']} files, {human_size(stats['bytes'])}")
    md.append("\n## Tree\n")
    md.append(build_tree_md(Path(snap.root), snap.files))

    with md_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md))

    return json_path, md_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Project folder snapshot utility")
    p.add_argument("--root", type=Path, default=Path.cwd(), help="Project root directory")
    p.add_argument("--hashes", dest="hashes", action="store_true", help="Compute SHA-256 for files")
    p.add_argument("--no-hashes", dest="hashes", action="store_false", help="Do not compute hashes (default)")
    p.set_defaults(hashes=False)
    p.add_argument("--max-preview-bytes", type=int, default=1024, help="Max bytes to read for text preview")
    p.add_argument("--exclude", action="append", default=[], help="Names/globs to exclude; can repeat")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    excludes = set(DEFAULT_EXCLUDES)
    excludes.update(args.exclude)
    snap = collect_snapshot(args.root, excludes, args.max_preview_bytes, args.hashes)
    json_path, md_path = write_outputs(Path(snap.root), snap)
    print(json.dumps({
        "json": str(json_path),
        "markdown": str(md_path),
        "root": snap.root,
        "generated_at": snap.generated_at,
        "total_files": snap.total_files,
        "total_dirs": snap.total_dirs,
        "total_bytes": snap.total_bytes,
    }, indent=2))


if __name__ == "__main__":
    main()
