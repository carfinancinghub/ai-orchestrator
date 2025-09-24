import os, time
from github import Github
gh   = Github(os.environ["GITHUB_TOKEN"])
repo = gh.get_repo("carfinancinghub/cfh")
base = repo.get_branch(repo.default_branch)
branch = "sanity-" + str(int(time.time()))
try:
    repo.create_git_ref(ref=f"refs/heads/{branch}", sha=base.commit.sha)
    print("OK: created ref", branch)
except Exception as e:
    print("ERROR creating ref:", e)
