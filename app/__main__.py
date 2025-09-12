import os
from .duplicate_elimination import duplicate_elimination

def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dedupe", action="store_true", help="Run duplicate elimination")
    args = ap.parse_args()

    if args.dedupe:
        roots = os.environ.get("AIO_SCAN_ROOTS","").split(";")
        out_root = r"C:\cfh_consolidated"
        reports_root = os.environ.get("REPORTS_ROOT","reports")
        duplicate_elimination(roots, out_root, reports_root)
        return

    print("Nothing to do. Try: python -m app --dedupe")

if __name__ == "__main__":
    main()
