from github import Github, Auth
import os, glob, pathlib
gh   = Github(auth=Auth.Token(os.environ["GITHUB_TOKEN"]))
repo = gh.get_repo(os.environ.get("AIO_TARGET_REPO","carfinancinghub/cfh"))
files = sorted(glob.glob("reports/upload_*.txt"), key=lambda p: pathlib.Path(p).stat().st_mtime, reverse=True)
pr = repo.get_pull(int(pathlib.Path(files[0]).read_text(encoding="utf-8").strip().split("/")[-1]))
def ensure_label(name, color):
    try: return repo.get_label(name)
    except Exception: return repo.create_label(name=name, color=color)
pr.add_to_labels(ensure_label("ts-migration","0E8A16"), ensure_label("analysis","5319E7"))
print("Labeled PR", pr.number)
