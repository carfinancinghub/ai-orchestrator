import json
from app.ops import process_batch_ext
run_id = "20250914_150205"
cands  = json.loads(r'''["C:\\Backup_Projects\\CFH\\frontend\\src\\components\\mechanic\\AIDiagnosticsAssistant.tsx","C:\\Backup_Projects\\CFH\\frontend\\src\\components\\InspectionPhotoPreviewer.tsx","C:\\Backup_Projects\\CFH\\frontend\\src\\App.tsx","C:\\Backup_Projects\\CFH\\frontend\\src\\main.tsx"]''')
res = process_batch_ext("local", None, cands, {}, run_id, batch_limit=999, mode="generate")
print("groups:", len(res))
