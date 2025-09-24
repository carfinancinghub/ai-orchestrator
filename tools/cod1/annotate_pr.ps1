param(
  [int]$PR = 16,
  [string]$Label = "cod1-continuity"
)
$ErrorActionPreference = "Stop"
$NOTE = @"
Cod1 Continuity update:
- Reviewed → Suggested → Spec'd → Generated → Verified
- Artifacts: artifacts/suggestions/, artifacts/specs/, artifacts/generated/, artifacts/reviews/
- Guard: no overwrites; review always precedes generation.
"@
gh pr comment $PR --body $NOTE
try { if ($Label) { gh pr edit $PR --add-label $Label } } catch {}
