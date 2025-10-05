. scripts\gh-grounded.ps1  # dot-source

# show a small patch around the /prune function in api/routes.py
Show-ContextPatch -Path "api/routes.py" -Find "def prune(" -Context 6

# capture an edit session into a log, and push the log
Start-GhTranscript -Label "auctions-pilot"
# ... run your build_ts/prune/prep etc. ...
Stop-GhTranscript   # prints a raw link you can paste back to me
