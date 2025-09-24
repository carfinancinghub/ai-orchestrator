import importlib, sys
try:
    m = importlib.import_module("app.ops")
    print("OK import; chooser?", hasattr(m, "_cod1_branch_for_run"))
    sys.exit(0)
except Exception as e:
    print("IMPORT ERROR:", e)
    sys.exit(1)
