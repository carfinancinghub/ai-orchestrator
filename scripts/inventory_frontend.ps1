param([string]$Root = "C:\Backup_Projects\CFH\frontend\src")
$ErrorActionPreference="Stop"
$invDir="reports"; $dbgDir="reports\debug"
New-Item -ItemType Directory -Force -Path $invDir,$dbgDir | Out-Null
function Get-QuickHash([string]$path){
  try{
    $sha1=[System.Security.Cryptography.SHA1]::Create()
    $fs=[System.IO.File]::OpenRead($path)
    try{
      $buf=New-Object byte[] 1048576
      $read=$fs.Read($buf,0,$buf.Length)
      $sha1.TransformFinalBlock($buf,0,$read)
      ($sha1.Hash|ForEach-Object ToString x2)-join""
    }finally{$fs.Dispose();$sha1.Dispose()}
  }catch{""}
}
$files=Get-ChildItem $Root -File -Recurse -ErrorAction SilentlyContinue |
  Where-Object { $_.FullName -notmatch '\\node_modules\\' -and $_.FullName -notmatch '\\dist\\' -and -not $_.Attributes.HasFlag([IO.FileAttributes]::Hidden) }
$rows=foreach($f in $files){
  [pscustomobject]@{
    path=$f.FullName
    rel=$f.FullName.Substring($Root.Length).TrimStart('\','/')
    ext=$f.Extension.ToLower()
    size=$f.Length
    mtime=$f.LastWriteTimeUtc.ToString("yyyy-MM-ddTHH:mm:ssZ")
    sha1=Get-QuickHash $f.FullName
    base=[IO.Path]::GetFileNameWithoutExtension($f.Name).ToLower()
  }
}
$csv="$invDir\inv_frontend_files.csv"
$rows | Export-Csv -NoTypeInformation -Encoding UTF8 $csv
$extCsv="$invDir\inv_frontend_ext_summary.csv"
$rows | Group-Object ext | ForEach-Object {
  [pscustomobject]@{ ext=$_.Name; count=$_.Count; bytes=($_.Group|Measure-Object size -Sum).Sum }
} | Sort-Object bytes -Descending | Export-Csv -NoTypeInformation -Encoding UTF8 $extCsv
$pref=@(".ts",".tsx",".js",".jsx"); $rank=@{}; 0..($pref.Count-1) | ForEach-Object { $rank[$pref[$_]]=$_ }
$groups=$rows | Group-Object { "$($_.base)|$($_.size)" }
$kept=[System.Collections.Generic.List[string]]::new()
$dups=[System.Collections.Generic.List[psobject]]::new()
foreach($g in $groups){
  $grp=$g.Group | Sort-Object { if($rank.ContainsKey($_.ext)){$rank[$_.ext]} else {999} }
  $keep=$grp[0]; $kept.Add($keep.path)
  if($grp.Count -gt 1){
    $drop=($grp|Select-Object -Skip 1).path -join ";"
    $dups.Add([pscustomobject]@{ key=$g.Name; kept=$keep.path; dropped=$drop })
  }
}
$dupeCsv="$invDir\inv_frontend_dupes.csv"
$dups | Export-Csv -NoTypeInformation -Encoding UTF8 $dupeCsv
$convList="$invDir\conversion_candidates.txt"
$kept | Set-Content -Encoding UTF8 $convList
"OK: wrote $csv, $extCsv, $dupeCsv, $convList"
