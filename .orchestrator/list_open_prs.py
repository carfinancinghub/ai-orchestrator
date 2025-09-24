from github import Github, Auth
import os
gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
repo = gh.get_repo(os.environ.get("AIO_TARGET_REPO","carfinancinghub/cfh"))
for pr in repo.get_pulls(state="open"):
    print(f"#{pr.number}  head={pr.head.label}  base={pr.base.label}  title={pr.title}")
