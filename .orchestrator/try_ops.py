from app.ops import process_batch_ext
run_id = "20250914_023019"
candidates = [
  r"C:\Backup_Projects\CFH\frontend\src\App.tsx",
  r"C:\Backup_Projects\CFH\frontend\src\main.tsx",
  r"C:\Backup_Projects\CFH\frontend\src\components\mechanic\AIDiagnosticsAssistant.tsx",
  r"C:\Backup_Projects\CFH\frontend\src\components\InspectionPhotoPreviewer.tsx",
]
out = process_batch_ext(
    platform="local",
    token=None,
    candidates=candidates,
    bundle_by_src={},
    run_id=run_id,
    batch_limit=50,
    mode="all",
)
for item in out:
    print(item.get("generated") or item.get("staged") or item.get("base") or "")
