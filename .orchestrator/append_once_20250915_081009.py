from app.ops import process_batch_ext, sgman_after_append
res = process_batch_ext("local", None, [r'C:\Backup_Projects\CFH\frontend\src\components\mechanic\AIDiagnosticsAssistant.tsx'], {}, "20250915_081009", batch_limit=25, mode="generate")
print("batch:", res)
# Optional: immediately run gates + comment + labels
try:
    sgman_after_append("20250915_081009")
except Exception as e:
    print("sgman_after_append warn:", e)
