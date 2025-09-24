import os, json, re, pathlib
from github import Github, Auth

run_id = "20250914_145631"
token  = os.environ["GITHUB_TOKEN"]
repo_name = os.environ.get("AIO_TARGET_REPO", "carfinancinghub/cfh")
branch = os.environ.get("AIO_UPLOAD_BRANCH", "ts-migration/generated-staging")

gh   = Github(auth=Auth.Token(token))
repo = gh.get_repo(repo_name)

# Find PR by head branch
pr = None
for _pr in repo.get_pulls(state="open", head=f"{repo.owner.login}:{branch}", base=repo.default_branch):
    pr = _pr
    break
assert pr, "Rolling PR not found."

gates_path = pathlib.Path(f"reports/gates_{run_id}.json")
data = json.loads(gates_path.read_text(encoding="utf-8"))
b = data["steps"]["build"]; t = data["steps"]["test"]; l = data["steps"]["lint"]

body = f"""**Gates report {run_id}**

- build: pass={b['pass']} exit={b['exit']}
- test : pass={t['pass']} exit={t['exit']}
- lint : pass={l['pass']} exit={l['exit']}

(Frontend: {data.get('frontend','?')}; npm: {(data.get('tooling') or {}).get('npm_bin','?')})"""

pr.create_issue_comment(body)
print("commented on PR", pr.number)
