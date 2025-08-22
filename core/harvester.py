# Path: core/harvester.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List
import ast

_SKIP_DIRS = {"venv",".git","__pycache__",".pytest_cache","node_modules","artifacts","reports"}
_SKIP_FILES_END = ("_test.py","tests.py")

@dataclass
class Item:
    path: Path; name: str; kind: str; lineno: int; end_lineno: int; score: int

class Harvester:
    def __init__(self, root: Path) -> None: self.root = Path(root)

    def _iter_python(self) -> Iterable[Path]:
        for p in self.root.rglob("*.py"):
            if any(seg in _SKIP_DIRS for seg in p.parts): continue
            if p.name.startswith(".") or p.name=="conftest.py" or p.name.endswith(_SKIP_FILES_END): continue
            yield p

    def _score_node(self, node: ast.AST) -> int:
        class C(ast.NodeVisitor):
            def __init__(self): self.c=1
            def generic_visit(self,n):
                if isinstance(n,(ast.If,ast.For,ast.While,ast.With,ast.Try,ast.BoolOp,ast.Match)): self.c+=1
                super().generic_visit(n)
        c=C(); c.visit(node); return c.c

    def _extract_items(self, path: Path) -> List[Item]:
        try: tree=ast.parse(path.read_text(encoding="utf-8",errors="replace"))
        except Exception: return []
        out: List[Item]=[]
        for n in tree.body:
            if isinstance(n, ast.FunctionDef) and not n.name.startswith("_"):
                out.append(Item(path,n.name,"function",n.lineno,getattr(n,"end_lineno",n.lineno),
                                self._score_node(n)+(1 if ast.get_docstring(n) else 0)))
            elif isinstance(n, ast.ClassDef) and not n.name.startswith("_"):
                out.append(Item(path,n.name,"class",n.lineno,getattr(n,"end_lineno",n.lineno),
                                self._score_node(n)+(1 if ast.get_docstring(n) else 0)))
        return out

    def scan(self) -> List[Item]:
        items: List[Item]=[]
        for p in self._iter_python(): items.extend(self._extract_items(p))
        items.sort(key=lambda i:(i.score, i.kind=="class"), reverse=True)
        return items

    def bundle(self, items: List[Item], limit: int=20) -> str:
        by: Dict[Path,List[Item]]={}; [by.setdefault(i.path,[]).append(i) for i in items[:limit]]
        lines=["# Generated bundle — extracted reusable items\n"]
        for path, its in by.items():
            src=path.read_text(encoding="utf-8",errors="replace").splitlines()
            lines.append(f"\n# ---- From: {path} ----\n")
            for it in its:
                block=src[max(it.lineno-1,0):max(it.end_lineno,it.lineno)]
                if block and block[-1].strip(): block.append("")
                lines.extend(block)
        return "\n".join(lines)
