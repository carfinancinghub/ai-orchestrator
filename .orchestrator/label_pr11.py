from github import Github, Auth
import os
gh   = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
repo = gh.get_repo(os.environ.get("AIO_TARGET_REPO","carfinancinghub/cfh"))
pr   = repo.get_pull(11)

def ensure_label(name, color):
    try: return repo.get_label(name)
    except Exception: return repo.create_label(name=name, color=color)

pr.add_to_labels(
    ensure_label("ts-migration","0E8A16"),
    ensure_label("analysis","5319E7"),
)
print("Labeled PR", pr.number)
