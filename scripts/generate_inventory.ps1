# Define output file path
$outputFile = "FileInventory.txt"

# Get all files excluding node_modules, venv, .mypy_cache, .ruff_cache, __pycache__, and .git subfolders, write to file
Get-ChildItem -Recurse -File -Force | Where-Object { $_.FullName -notmatch '\\node_modules\\|\\.venv\\|\\venv\\|\\.mypy_cache\\|\\.ruff_cache\\|__pycache__\\|\\.git\\' } | ForEach-Object { "$($_.FullName) | $($_.Length) bytes" } | Set-Content -Path $outputFile

# Confirm completion
Write-Host "DONE: File inventory saved to $outputFile"