import importlib, sys
try:
    m = importlib.import_module("app.ops")
    print("OK import; helpers:", all(hasattr(m, x) for x in [
        "_cod1_branch_for_run","process_batch_ext","upload_to_github","run_gates","sgman_after_append"
    ]))
    sys.exit(0)
except Exception as e:
    print("IMPORT ERROR:", e)
    sys.exit(1)
