# app/review_cli.py
import argparse, sys
from app.review_multi import run_multi_ai_review

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="+", required=True)
    ap.add_argument("--out", default="artifacts/reviews")
    args = ap.parse_args()
    run_id = run_multi_ai_review(args.files, out_root=args.out)
    print({"ok": True, "run_id": run_id})

if __name__ == "__main__":
    main()
