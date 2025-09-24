import json
from app.ops import process_batch_ext, multi_ai_review_bundle
run_id = "20250914_141335"
files  = json.loads(r'["C:\\Backup_Projects\\CFH\\frontend\\src\\components\\mechanic\\AIDiagnosticsAssistant.tsx","C:\\Backup_Projects\\CFH\\frontend\\src\\components\\InspectionPhotoPreviewer.tsx","C:\\Backup_Projects\\CFH\\frontend\\src\\App.tsx","C:\\Backup_Projects\\CFH\\frontend\\src\\main.tsx"]')
print("review bundle:", multi_ai_review_bundle(files, run_id))
res = process_batch_ext("local", None, files, {}, run_id, batch_limit=999, mode="generate")
print("generated items:", len(res))
