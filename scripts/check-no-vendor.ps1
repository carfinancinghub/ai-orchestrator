Param()
# Blocks vendored/compiled trees from sneaking into tracked sets
git ls-files -- . 
| Where-Object {
     -like 'node_modules/*' -or
     -like '.venv/*' -or
     -like 'artifacts/*'
  } 
| ForEach-Object { Write-Error "Vendored path tracked: "; exit 1 }

Write-Host "No tracked vendor artifacts detected."