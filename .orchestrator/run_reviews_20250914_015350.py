from app.review_multi import run
import sys, pathlib
run_id = "20250914_015350"
root = r"C:\Backup_Projects\CFH\frontend"
files = [
r'C:\Backup_Projects\CFH\frontend\src\components\mechanic\AIDiagnosticsAssistant.tsx',
r'C:\Backup_Projects\CFH\frontend\src\components\InspectionPhotoPreviewer.tsx',
r'C:\Backup_Projects\CFH\frontend\src\App.tsx',
r'C:\Backup_Projects\CFH\frontend\src\main.tsx',
]
out = run(files, run_id, root)
print("\n".join(out))
