from github import Github, Auth
import os, re
gh   = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
repo = gh.get_repo(os.environ.get("AIO_TARGET_REPO","carfinancinghub/cfh"))

for pr in repo.get_pulls(state="open"):
    if re.match(r"ts-migration/generated-\d{8}_\d{6}", pr.head.ref):
        pr.edit(state="closed")
        print("Closed", pr.number, pr.head.ref)
