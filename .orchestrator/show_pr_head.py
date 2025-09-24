from github import Github, Auth
import os
gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
repo = gh.get_repo(os.environ.get("AIO_TARGET_REPO","carfinancinghub/cfh"))
pr   = repo.get_pull(15)
print("PR #", pr.number)
print("head.ref =", pr.head.ref)
print("title    =", pr.title)
