from github import Github, Auth
import os
gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
repo = gh.get_repo(os.environ.get("AIO_TARGET_REPO","carfinancinghub/cfh"))
pr   = repo.get_pull(int("https://github.com/carfinancinghub/cfh/pull/16".split("/")[-1]))
print("PR #", pr.number, "head.ref =", pr.head.ref, "base =", pr.base.ref, "url =", pr.html_url)
