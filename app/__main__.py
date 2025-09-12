import os
import argparse

def _maybe_import_duplicate_elimination():
    try:
        from .duplicate_elimination import duplicate_elimination
        return duplicate_elimination
    except Exception:
        return None

def _scan_reviews():
    from .review_multi import scan_and_review
    scan_and_review()

def _upload_generated():
    from .upload_generated import upload_generated
    upload_generated(branch=os.environ.get("AIO_UPLOAD_BRANCH","ts-migration/generated"),
                     dry_run=os.environ.get("AIO_DRY_RUN","false").lower()=="true")

def main():
    ap = argparse.ArgumentParser(description="CFH Orchestrator CLI")
    ap.add_argument("--dedupe", action="store_true", help="Run duplicate elimination")
    ap.add_argument("--scan-reviews", action="store_true", help="Scan artifacts and write multi-AI reviews")
    ap.add_argument("--upload-generated", action="store_true", help="Upload artifacts/generated to branch")
    args = ap.parse_args()

    did_any = False

    if args.dedupe:
        did_any = True
        de = _maybe_import_duplicate_elimination()
        if de:
            roots = os.environ.get("AIO_SCAN_ROOTS","").split(";")
            out_root = r"C:\cfh_consolidated"
            reports_root = os.environ.get("REPORTS_ROOT","reports")
            de(roots, out_root, reports_root)
        else:
            print("[dedupe] duplicate_elimination not available")

    if args.scan_reviews:
        did_any = True
        _scan_reviews()

    if args.upload_generated:
        did_any = True
        _upload_generated()

    if not did_any:
        print("Nothing to do. Try one of: --scan-reviews | --upload-generated | --dedupe")

if __name__ == "__main__":
    main()
