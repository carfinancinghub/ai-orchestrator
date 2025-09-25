Param([string]$Path = "reports\ai_review_20250923_084351.md")
$opens  = (Select-String $Path -Pattern '^\s*```ts\s+path=@' -AllMatches).Matches.Count
$closes = (Select-String $Path -Pattern '^\s*```\s*$' -AllMatches).Matches.Count
"Fences — ts: $opens | closing: $closes"
