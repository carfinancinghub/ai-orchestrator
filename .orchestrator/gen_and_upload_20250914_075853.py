from app.ops import process_batch_ext
run_id = "20250914_075853"
cands  = [
r'C:\Backup_Projects\CFH\frontend\src\components\mechanic\AIDiagnosticsAssistant.tsx',
r'C:\Backup_Projects\CFH\frontend\src\components\InspectionPhotoPreviewer.tsx',
r'C:\Backup_Projects\CFH\frontend\src\App.tsx',
r'C:\Backup_Projects\CFH\frontend\src\main.tsx',
]
res = process_batch_ext("local", None, cands, {}, run_id, batch_limit=999, mode="generate")
print("items:", len(res))
