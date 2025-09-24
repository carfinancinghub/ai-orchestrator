from app.ops import process_batch_ext
res = process_batch_ext("local", None, [r'C:\Backup_Projects\CFH\frontend\src\components\mechanic\AIDiagnosticsAssistant.tsx'], {}, "20250914_201056", batch_limit=999, mode="generate")
print("items:", len(res))
