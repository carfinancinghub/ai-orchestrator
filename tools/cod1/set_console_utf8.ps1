# Make console paste/render more deterministic
chcp 65001 | Out-Null
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
try { $global:PSStyle.OutputRendering = 'PlainText' } catch {}
Write-Host "Console set to UTF-8 and plain text rendering for this session."
