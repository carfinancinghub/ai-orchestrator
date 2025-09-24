Cod1 Continuity – PowerShell Toolkit
====================================

Run each script like this in PowerShell:

    Set-ExecutionPolicy -Scope Process Bypass -Force
    .\<script>.ps1

Edit the variables at the top of each script to fit your machine.

Included scripts:
- cod1_bootstrap.ps1        : Bootstraps helper module, hooks ops.py, commits & pushes (copied from earlier).
- run_cod1_batch.ps1        : Picks N .jsx/.js files and runs process_batch_ext(..., mode='cod1').
- count_artifacts.ps1       : Shows counts of suggestions/specs/generated/reviews for a run id (or latest).
- annotate_pr.ps1           : Comments on a PR and adds a label (requires GitHub CLI 'gh').
- set_console_utf8.ps1      : Makes console paste/rendering more deterministic (UTF‑8, plain text).
- fix_git_hook_clean_output.ps1 : Normalizes git hooks to stdout to avoid noisy stderr.
- cleanup_cod1_placeholders.ps1 : Removes placeholder-generated files from artifacts/generated.
