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
# --- Cod1 hooks ---
try:
    import argparse, os
    from .review_multi import scan_and_review
    from .upload_generated import upload_generated
    def _cod1_cli():
        ap = argparse.ArgumentParser(add_help=False)
        ap.add_argument("--scan-reviews", action="store_true")
        ap.add_argument("--upload-generated", action="store_true")
        ns, _ = ap.parse_known_args()
        if ns.scan_reviews:
            scan_and_review(); raise SystemExit(0)
        if ns.upload_generated:
            upload_generated(branch=os.environ.get("AIO_UPLOAD_BRANCH","ts-migration/generated"),
                             dry_run=os.environ.get("AIO_DRY_RUN","false").lower()=="true")
            raise SystemExit(0)
    _cod1_cli()
except Exception:
    pass
