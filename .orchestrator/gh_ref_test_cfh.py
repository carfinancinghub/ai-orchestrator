import os, time
from github import Github
gh = Github(os.environ["GITHUB_TOKEN"])
repo = gh.get_repo("carfinancinghub/cfh")
sha  = repo.get_branch(repo.default_branch).commit.sha
ref  = f"refs/heads/sanity-{int(time.time())}"
repo.create_git_ref(ref, sha)
print("OK on cfh:", ref)
