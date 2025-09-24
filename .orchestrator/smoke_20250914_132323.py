from app.ops import multi_ai_review_bundle, generate_ts_file, review_generated_file
files = [r'C:\Backup_Projects\CFH\frontend\src\components\mechanic\AIDiagnosticsAssistant.tsx']
print(multi_ai_review_bundle(files, '20250914_132323'))
ts_path = generate_ts_file(r'C:\Backup_Projects\CFH\frontend\src\components\mechanic\AIDiagnosticsAssistant.tsx', {'Free': {'summary': 'add basic props typing'}})
print('generated:', ts_path)
print(review_generated_file(ts_path, {'Free': {'summary': 'add basic props typing'}}, 'offline', '20250914_132323'))
