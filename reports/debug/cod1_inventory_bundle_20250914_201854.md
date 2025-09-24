## Frontend Summary
- Files CSV: eports/inv_frontend_files.csv
- Ext Summary: eports/inv_frontend_ext_summary.csv
- Dupes (basename+size): eports/inv_frontend_dupes.csv
- Conversion candidates: eports/conversion_candidates.txt
"@

 = Get-Content "reports\debug\inventory_orchestrator_summary.md" -Raw
 = (Import-Csv "reports\inv_frontend_ext_summary.csv" | Select-Object -First 12 | ConvertTo-Csv -NoTypeInformation) -join "
"
 = (Import-Csv "reports\inv_frontend_dupes.csv" | Select-Object -First 10 | ConvertTo-Csv -NoTypeInformation) -join "
"

@"
# Cod1 Inventory Bundle (20250914_201854)



### Top extensions (sample)

### Duplicate groups (sample)

## Orchestrator Snapshot


## Notes
- Paths are absolute for reproducibility.
- SHA1 is a quick partial hash for triage.
- Full CSVs are included alongside this file.
