import os, json, pathlib
from github import Github, Auth

token   = os.environ["GITHUB_TOKEN"]
repo_nm = os.environ.get("AIO_TARGET_REPO", "carfinancinghub/cfh")
pr_num  = 11
run_id  = "20250914_145631"

gh   = Github(auth=Auth.Token(token))
repo = gh.get_repo(repo_nm)
pr   = repo.get_pull(pr_num)

gates_path = pathlib.Path(f"reports/gates_{run_id}.json")
data = json.loads(gates_path.read_text(encoding="utf-8"))
b = data["steps"]["build"]; t = data["steps"]["test"]; l = data["steps"]["lint"]

body = f"""**Gates report {run_id}**

- build: pass={b['pass']} exit={b['exit']}
- test : pass={t['pass']} exit={t['exit']}
- lint : pass={l['pass']} exit={l['exit']}

(Frontend: {data.get('frontend','?')}; npm: {(data.get('tooling') or {}).get('npm_bin','?')})"""

pr.create_issue_comment(body)
print("Commented on PR", pr.number)
