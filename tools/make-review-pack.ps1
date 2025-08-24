# tools\make-review-pack.ps1
param(
  [string]$Project = 'CFH'
)
Set-Location C:\c\ai-orchestrator
[Environment]::CurrentDirectory = (Get-Location).Path

$stamp    = Get-Date -Format yyyyMMdd_HHmmss
$inJson   = Join-Path $PWD "reports\$Project\review_input_$stamp.json"
$outMd    = Join-Path $PWD "reports\$Project\review-pack.md"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$codemap = [IO.File]::ReadAllText("reports\$Project\codemap.json",[Text.Encoding]::UTF8) -replace '^\uFEFF',''
$prompt  = [IO.File]::ReadAllText("prompts\review.md",[Text.Encoding]::UTF8)             -replace '^\uFEFF',''

$body = ConvertTo-Json -Depth 50 ([pscustomobject]@{ project=$Project; codemap=$codemap; prompt=$prompt })
New-Item -ItemType Directory -Force -Path (Split-Path $inJson) | Out-Null
[IO.File]::WriteAllText($inJson, $body, $utf8NoBom)

node tools/make-review-pack.mjs $inJson $outMd
"JSON : $inJson"
"MD   : $outMd"
