#!/usr/bin/env python
"""
Normalize 'bancada' to always be a list of objects.

Usage:
  python -m backend.process.normalize_bancadas --input data/congresistas_2021_2026.json
  python -m backend.process.normalize_bancadas --input data/congresistas_2021_2026.json --output data/out.json
  python -m backend.process.normalize_bancadas --input data/congresistas_2021_2026.json --dry-run
  python -m backend.process.normalize_bancadas --input data/congresistas_2021_2026.json --strict
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, List, Tuple


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def normalize_bancada_value(value: Any) -> Tuple[List[dict], List[str]]:
    warnings: List[str] = []
    if value is None:
        return [], warnings
    if isinstance(value, list):
        # Filter to dicts, but keep list length info in warnings.
        bad = [v for v in value if not isinstance(v, dict)]
        if bad:
            warnings.append(f"bancada list contains {len(bad)} non-object entries")
            value = [v for v in value if isinstance(v, dict)]
        return value, warnings
    if isinstance(value, dict):
        return [value], warnings
    warnings.append(f"bancada is {type(value).__name__}, replaced with empty list")
    return [], warnings


def validate_bancada_items(items: List[dict], strict: bool) -> List[str]:
    warnings: List[str] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            warnings.append(f"bancada[{i}] is {type(item).__name__}")
            continue
        if "name" not in item:
            msg = f"bancada[{i}] missing 'name'"
            if strict:
                raise ValueError(msg)
            warnings.append(msg)
        if "periodo" not in item:
            msg = f"bancada[{i}] missing 'periodo'"
            if strict:
                raise ValueError(msg)
            warnings.append(msg)
    return warnings


def normalize_records(records: List[dict], strict: bool) -> Tuple[List[dict], List[str]]:
    warnings: List[str] = []
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            if strict:
                raise ValueError(f"record[{idx}] is {type(rec).__name__}")
            warnings.append(f"record[{idx}] is {type(rec).__name__}")
            continue
        if "bancada" not in rec:
            rec["bancada"] = []
            warnings.append(f"record[{idx}] missing 'bancada', set to []")
            continue
        normalized, w = normalize_bancada_value(rec["bancada"])
        rec["bancada"] = normalized
        warnings.extend([f"record[{idx}] {msg}" for msg in w])
        warnings.extend([f"record[{idx}] {msg}" for msg in validate_bancada_items(normalized, strict)])
    return records, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize bancada to be a list in congresistas JSON.")
    parser.add_argument("--input", required=True, help="Input JSON file path.")
    parser.add_argument("--output", help="Output JSON file path (defaults to input).")
    parser.add_argument("--dry-run", action="store_true", help="Do not write output; only report.")
    parser.add_argument("--strict", action="store_true", help="Fail on missing required fields.")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output) if args.output else in_path

    data = load_json(in_path)
    if not isinstance(data, list):
        raise ValueError("Top-level JSON is not a list")

    normalized, warnings = normalize_records(data, strict=args.strict)

    if warnings:
        print("Warnings:")
        for w in warnings:
            print(f"- {w}")
    else:
        print("No warnings.")

    if args.dry_run:
        print("Dry run: no output written.")
        return 0

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
