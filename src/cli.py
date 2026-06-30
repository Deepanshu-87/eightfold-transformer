"""CLI entrypoint.

Examples:

  # Default schema:
  python -m src.cli \\
    --csv samples/recruiter.csv \\
    --ats samples/ats.json \\
    --resumes samples/resumes \\
    --notes samples/notes \\
    --out outputs/default_output.json

  # Custom config:
  python -m src.cli \\
    --csv samples/recruiter.csv --ats samples/ats.json \\
    --resumes samples/resumes --notes samples/notes \\
    --config configs/custom.json \\
    --out outputs/custom_output.json
"""
from __future__ import annotations

import argparse
import json
import sys

from .pipeline import run, write_json


def _load_json(path: str | None) -> dict | None:
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="candidate-transformer",
        description="Multi-source candidate data transformer.",
    )
    p.add_argument("--csv", help="Path to recruiter CSV", default=None)
    p.add_argument("--ats", help="Path to ATS JSON", default=None)
    p.add_argument("--resumes", help="Path to resume .txt file or dir", default=None)
    p.add_argument("--notes", help="Path to recruiter notes .txt or dir", default=None)
    p.add_argument("--config", help="Projection config JSON", default=None)
    p.add_argument("--out", help="Output JSON path", default=None)
    p.add_argument("--strict", action="store_true", help="Raise on validation errors")
    args = p.parse_args(argv)

    if not any([args.csv, args.ats, args.resumes, args.notes]):
        p.error("Provide at least one source (--csv, --ats, --resumes, --notes).")

    config = _load_json(args.config)
    result = run(
        inputs={"csv": args.csv, "ats": args.ats, "resumes": args.resumes, "notes": args.notes},
        config=config,
        strict=args.strict,
    )
    payload = {
        "count": result["count"],
        "records": result["records"],
        "schema_errors": result["errors"],
    }
    if args.out:
        write_json(payload, args.out)
        print(f"Wrote {result['count']} record(s) to {args.out}")
        if result["errors"]:
            print(f"[warn] {len(result['errors'])} schema validation issue(s):")
            for e in result["errors"][:5]:
                print("  -", e)
    else:
        json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
