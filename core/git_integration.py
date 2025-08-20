"""
Path: core/git_integration.py
Lightweight GitHub/GitLab/Local commit + PR/MR utilities. Safe to import without tokens.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import subprocess


@dataclass
class PRResult:
    ok: bool
    provider: str
    url: Optional[str]
    reason: Optional[str] = None


def _local_git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)


def commit_branch_local(root: Path, branch: str, message: str) -> Dict[str, str]:
    _local_git("checkout", "-B", branch, cwd=root)
    add = _local_git("add", ".", cwd=root)
    commit = _local_git("commit", "-m", message, cwd=root)
    return {"add": add.stdout + add.stderr, "commit": commit.stdout + commit.stderr}


def create_pr_github(repo_full: str, token: str, base: str, head: str, title: str, body: str) -> PRResult:
    try:
        from github import Github  # type: ignore
    except Exception as exc:  # pragma: no cover
        return PRResult(False, "github", None, f"PyGithub-missing: {exc}")
    try:
        gh = Github(token)
        repo = gh.get_repo(repo_full)
        pr = repo.create_pull(title=title, body=body, base=base, head=head)
        return PRResult(True, "github", pr.html_url)
    except Exception as exc:  # pragma: no cover
        return PRResult(False, "github", None, str(exc))


def create_mr_gitlab(repo_http_url: str, token: str, base: str, head: str, title: str, body: str) -> PRResult:
    try:
        import gitlab  # type: ignore
    except Exception as exc:  # pragma: no cover
        return PRResult(False, "gitlab", None, f"python-gitlab-missing: {exc}")
    try:
        gl = gitlab.Gitlab.from_config()  # or use token + url envs in real setup
        projects = gl.projects.list(search=repo_http_url.split('/')[-1])
        if not projects:
            return PRResult(False, "gitlab", None, "project-not-found")
        project = projects[0]
        mr = project.mergerequests.create({"source_branch": head, "target_branch": base, "title": title, "description": body})
        return PRResult(True, "gitlab", mr.web_url)
    except Exception as exc:  # pragma: no cover
        return PRResult(False, "gitlab", None, str(exc))

