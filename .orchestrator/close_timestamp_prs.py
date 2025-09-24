from github import Github, Auth
import os, re
gh = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
repo = gh.get_repo(os.environ.get("AIO_TARGET_REPO","carfinancinghub/cfh"))

rolling = "ts-migration/generated-staging"
stamp_re = re.compile(r"^ts-migration/generated-\d{8}_\d{6}$")
closed = []
kept   = []

for pr in repo.get_pulls(state="open"):
    ref = pr.head.ref or ""
    if ref == rolling:
        kept.append((pr.number, ref, "rolling"))
        continue
    if stamp_re.match(ref):
        pr.edit(state="closed")
        closed.append((pr.number, ref))
    else:
        kept.append((pr.number, ref, "non-migration-or-fixed"))

print("Closed:", closed)
print("Kept:", kept)
