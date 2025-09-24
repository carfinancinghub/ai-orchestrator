from app.github_uploader import upload_generated_to_github
import os
rid = os.environ.get("RUN_ID")
path = upload_generated_to_github(rid)
print(path or "no-plan")
